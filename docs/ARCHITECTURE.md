# TRACR Architecture

This document describes the current TRACR runtime architecture: how jobs are launched, executed, and persisted across API, TUI, and web workflows.

## System Overview

TRACR is split into a control plane and a data plane:

- Control plane: job intake, scheduling, status tracking, and UI-facing APIs.
- Data plane: page rendering, OCR inference calls, and output persistence.

The core architectural decision is to use one OpenAI-compatible OCR call path for both hosted providers and local runtimes. The selected model target is expressed as `base_url + api_key + model`, which keeps orchestration logic consistent across providers.

## Component Map

### API and orchestration

- `tracr/app/api.py`: FastAPI application and HTTP endpoints.
- `tracr/runtime/job_manager.py`: job lifecycle state machine, run orchestration, progress counters, timing, and cancellation handling.
- `tracr/runtime/openai_client.py`: OpenAI-compatible request layer used by OCR workers and proxy mode.

### Local runtime management

- `tracr/runtime/vllm_manager.py`: vLLM server process lifecycle, GPU reservation/release, health checks, and endpoint handoff to workers.

### Input, config, and outputs

- `tracr/core/input_discovery.py`: resolves input paths and scans `inputs/`.
- `tracr/core/job_configs.py`: finds, loads, and validates YAML job configs from `job_configs/`.
- `tracr/core/pdf_tools.py`: page rendering utilities for PDF processing.
- `tracr/core/output_layout.py`: run numbering, output directory layout, and metadata writes.

### User interfaces

- `tracr/tui/app.py` and `tracr/tui/screens/*`: Textual launch and monitoring interface.
- `tracr/web/routes.py` and `tracr/web/*.py`: web output viewer and ELO review routes/components.

## Execution Flow

1. A client submits a job (`POST /api/jobs`) from the TUI or API.
2. `JobManager` normalizes request state, resolves inputs/config, and expands per-model runs.
3. For each run, workers render/extract PDF pages and issue OCR calls through the OpenAI-compatible client.
4. API targets call remote endpoints directly; local targets request a vLLM endpoint from `VLLMServerManager`.
5. Results are written incrementally as markdown pages with metadata updates at job/model/run/pdf levels.
6. Progress and ETA state is exposed through API endpoints and consumed by TUI/web views.

## Local Mode and GPU Scheduling

Local execution is capacity-aware:

- vLLM servers are started on demand per local model/run requirements.
- GPU resources are reserved before launch and released on completion/failure/cancel.
- Runs that cannot obtain required GPUs remain queued (`waiting_resources`) until capacity is available.
- OCR requests are bounded by configured concurrency to avoid overloading local runtimes.

If local runtime prerequisites are unavailable, TRACR degrades gracefully by surfacing clear run state/errors without corrupting job metadata.

## Output and Metadata Contract

Outputs are persisted as:

```text
outputs/<job_id>/<model_slug>/run-<run_num>/<pdf_slug>/<page_num>.md
```

Metadata files are written at:

- `outputs/<job_id>/job_metadata.json`
- `outputs/<job_id>/<model_slug>/model_metadata.json`
- `outputs/<job_id>/<model_slug>/run-<run_num>/run_metadata.json`
- `outputs/<job_id>/<model_slug>/run-<run_num>/<pdf_slug>/pdf_metadata.json`

Key invariants:

- Reusing a `job_id` appends new model runs via incremented `run_num`.
- API keys are never persisted into output metadata.
- The output path scheme remains stable for downstream automation and reviewer tooling.

## Web Reviewer and ELO

The web layer (`/web`) reads persisted outputs and provides:

- Side-by-side page image and markdown review.
- Rendered-vs-raw markdown toggles.
- Pairwise model voting for ELO ranking.

ELO artifacts are stored under:

```text
outputs/<job_id>/elo/
```

This includes ratings state and append-only vote history, using output hierarchy identities (job/model/run/pdf/page) as stable keys.

## Extension Points

Common extension seams:

- Add new provider presets by supplying `base_url`, auth key env var, and model defaults.
- Extend job config schema in `core/job_configs.py` and corresponding launch UI/API models.
- Add output post-processing while preserving the output layout contract.
- Add new reviewer workflows on top of existing output and metadata identities.
