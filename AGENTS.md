# AGENTS.md

## Project Identity

- Project name: **TRACR**
- Purpose: OCR orchestration for cloud/API providers and local vLLM models, with a Textual TUI for launch + monitoring.
- Python package name is `tracr`.

## Repo Layout

- `tracr/`
  - `app/api.py`: FastAPI app + API/web route registration
  - `cli.py`: CLI entrypoint (`tracr`)
  - `web_server.py`: standalone web launcher (`uv run web`)
  - `core/config.py`: environment-backed runtime settings and directory resolution
  - `core/models.py`: Pydantic request/response/state models
  - `core/provider_presets.py`: provider presets + default local model list
  - `core/input_discovery.py`: input path resolution and `inputs/` scanning
  - `core/job_configs.py`: YAML job config discovery/loading/validation
  - `core/output_layout.py`: output directory/run numbering/metadata writing
  - `core/pdf_tools.py`: PDF page rendering utilities
  - `runtime/job_manager.py`: job lifecycle, orchestration, progress/ETA state
  - `runtime/openai_client.py`: OpenAI-compatible OCR + proxy client
  - `runtime/vllm_manager.py`: local vLLM server process and GPU scheduling
  - `runtime/gpu.py`: GPU count/stat discovery (`nvidia-smi`/NVML fallback)
  - `runtime/elo_manager.py`: ELO rating persistence + vote updates
  - `tui/app.py`: main Textual app shell (home jobs view + orchestration)
  - `tui/common.py`: shared TUI helpers/constants (formatting, token stats, row key parsing)
  - `tui/service_client.py`: HTTP client for API endpoints used by the TUI
  - `tui/screens/launch_wizard.py`: launch wizard screen (inputs, configs, model queue, submission)
  - `tui/screens/job_runs.py`: per-job monitor screen (per-model progress + GPU + drilldown)
  - `tui/screens/output_viewer.py`: markdown page viewer for completed outputs
  - `tui/screens/outputs_browser.py`: output filesystem browser + preview
  - `web/routes.py`: web UI routes + ELO APIs
  - `web/page_shell.py`: shared web shell/header JS/CSS fragments
  - `web/page_viewer.py`: web output viewer section JS/markup
  - `web/page_elo.py`: ELO arena section JS/markup
- `inputs/`: source PDFs and nested input folders
- `outputs/`: generated markdown + metadata + ELO artifacts
- `job_configs/`: YAML launch config templates and saved launch definitions
- `media/`: README image assets
- `scripts/`: project helper scripts
- `tests/`: pytest tests
- `AGENTS.md`: canonical architecture + endpoint reference for contributors/agents

## Primary Commands

- Install deps: `uv sync`
- Install with web extras: `uv sync --extra web`
- Install with local runtime extras: `uv sync --extra local`
- Install with local + web extras: `uv sync --extra local --extra web`
- Run API + TUI together: `uv run tracr`
- Explicit equivalent of combined mode: `uv run tracr all`
- Run API: `uv run tracr api`
- Run TUI: `uv run tracr tui`
- Run web reviewer + ELO: `uv run tracr web` or `uv run web`
- Run standalone vLLM launcher: `uv run tracr vllm-launch <model> --num-gpus 1 --port 9000`
- Run all tests: `uv run tracr test`
- Run a test subset: `uv run tracr test -- -k <expr>`

## Coding Style

- Target Python `>=3.11`.
- Keep type hints on public functions and core state models.
- Prefer explicit, composable modules over large monolithic files.
- Follow existing Pydantic model patterns for request/response/state schemas.
- Keep comments concise and meaningful; avoid redundant comments.
- Keep files ASCII unless there is a strong reason not to.

## Architectural Invariants

- OpenAI-compatible routing is central: model providers should be swappable by `base_url + api_key`.
- Output structure must stay stable for downstream workflows:
  - `outputs/<job_id>/<model_slug>/run-<run_num>/<pdf_slug>/<page_num>.md`
  - metadata at job/model/run/pdf levels.
- ELO artifacts for a job live under `outputs/<job_id>/elo/` (`ratings.json`, `votes.jsonl`).
- Do not persist raw API keys to metadata/output files.
- Local mode should degrade gracefully when GPUs/vLLM are unavailable.
- If same `job_id` is reused, append new runs with incremented `run_num`.

## Runtime Architecture (Current)

TRACR runtime is split into:
- Control plane: job intake, scheduling, status, ETA/statistics, UI-facing APIs.
- Data plane: PDF page rendering, OCR inference calls, markdown/metadata persistence.

Core architectural model:
- One OpenAI-compatible OCR path is used for both hosted and local execution targets.
- Run targets are described as `base_url + api_key + model`; orchestration logic stays provider-agnostic.

Execution flow:
1. Client submits a launch request (`POST /api/jobs`) from TUI/API.
2. `JobManager` normalizes launch state and expands per-model runs.
3. Workers render/extract pages, call OCR via `OpenAICompatibleOCRClient`, and write outputs incrementally.
4. API targets call upstream endpoints directly; local targets request managed vLLM servers and GPU slots.
5. Metadata is updated at job/model/run/pdf levels as work progresses.
6. API, TUI, and web surfaces read shared persisted state for monitoring/review.

Local mode behavior:
- vLLM servers are started on demand and released when runs complete/fail/cancel.
- Runs can wait in `waiting_resources` when GPUs are unavailable.
- In-flight OCR request counts are bounded (`OCR_VLLM_MAX_CONCURRENT_REQUESTS`).
- GPU detection uses `nvidia-smi` first, with NVML fallback (`runtime/gpu.py`).

Extension points:
- Provider presets: `tracr/core/provider_presets.py`.
- Job config schema/loading: `tracr/core/job_configs.py`.
- Output post-processing: build on `tracr/core/output_layout.py` while preserving output path invariants.
- Reviewer UX: extend `tracr/web/page_*.py` and `tracr/web/routes.py`.

## Service Endpoints (Canonical Inventory)

Keep this list in sync with route decorators in:
- `tracr/app/api.py`
- `tracr/web/routes.py`

Core service + API:
- `GET /health`
- `GET /api/presets`
- `GET /api/local-default-models`
- `GET /api/inputs`
- `GET /api/job-configs`
- `POST /api/job-configs/load`
- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/cancel`
- `POST /api/jobs/{job_id}/dismiss`
- `GET /api/jobs/{job_id}/output-pages`
- `GET /api/jobs/{job_id}/output-pages/{page_index}`
- `GET /api/outputs/tree`
- `GET /api/outputs/file`
- `GET /api/system/gpus`
- `GET /api/providers/{provider_key}/key-status`
- `POST /api/proxy/chat/completions`

Web UI + ELO:
- `GET /web`
- `GET /web/`
- `GET /web/tracr.png`
- `GET /api/web/jobs`
- `GET /api/web/jobs/{job_id}/outputs`
- `GET /api/web/jobs/{job_id}/viewer/page`
- `GET /api/web/jobs/{job_id}/viewer/page-image`
- `GET /api/web/elo/jobs`
- `GET /api/web/elo/jobs/{job_id}/ratings`
- `GET /api/web/elo/jobs/{job_id}/next`
- `GET /api/web/elo/jobs/{job_id}/browse`
- `POST /api/web/elo/jobs/{job_id}/vote`

## Testing & Validation

- Add/adjust tests for behavior changes in orchestration, layout, and path discovery.
- For quick checks, run:
  - `python -m compileall -q tracr tests`
  - `uv run tracr test`
- Prefer deterministic tests with temporary directories for filesystem behavior.

## Agent Safety Rules

- Do not perform destructive git operations (e.g., `reset --hard`) unless explicitly requested.
- Do not modify unrelated files to satisfy formatting preferences.
- If working in a dirty tree, avoid reverting user changes you did not create.
