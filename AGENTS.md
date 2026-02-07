# AGENTS.md

## Project Identity

- Project name: **TRACR**
- Purpose: OCR orchestration for cloud/API providers and local vLLM models, with a Textual TUI for launch + monitoring.
- Python package name is `tracr`.

## Repo Layout

- `tracr/`
  - `app/api.py`: FastAPI app and HTTP endpoints
  - `runtime/job_manager.py`: job lifecycle, run orchestration, progress/ETA state
  - `runtime/openai_client.py`: OpenAI-compatible OCR + proxy client
  - `runtime/vllm_manager.py`: local vLLM server process and GPU scheduling
  - `core/output_layout.py`: output directory/run numbering/metadata writing
  - `core/input_discovery.py`: input path resolution and `inputs/` scanning
  - `core/job_configs.py`: YAML job config discovery/loading/validation
  - `core/pdf_tools.py`: PDF page rendering utilities
  - `tui/app.py`: main Textual app shell (home jobs view + orchestration)
  - `tui/common.py`: shared TUI helpers/constants (formatting, token stats, row key parsing)
  - `tui/service_client.py`: HTTP client for API endpoints used by the TUI
  - `tui/screens/launch_wizard.py`: launch wizard screen (inputs, configs, model queue, submission)
  - `tui/screens/job_runs.py`: per-job monitor screen (per-model progress + GPU + drilldown)
  - `tui/screens/output_viewer.py`: markdown page viewer for completed outputs
  - `tui/screens/outputs_browser.py`: output filesystem browser + preview
  - `web/routes.py`: web UI routes and ELO API endpoints
  - `web_server.py`: `uv run web` launcher for web reviewer + ELO UI
  - `cli.py`: CLI entrypoint (`tracr`)
- `job_configs/`: YAML launch config templates and saved launch definitions
- `tests/`: pytest tests
- `docs/ARCHITECTURE.md`: design notes
- `privasis/`: reference implementation; avoid modifying unless explicitly requested

## Primary Commands

- Install deps: `uv sync`
- Install with web extras: `uv sync --extra web`
- Install with local runtime extras: `uv sync --extra local`
- Install with local + web extras: `uv sync --extra local --extra web`
- Run API + TUI together: `uv run tracr`
- Run API: `uv run tracr api`
- Run TUI: `uv run tracr tui`
- Run web reviewer + ELO: `uv run web`
- Run standalone vLLM launcher: `uv run tracr vllm-launch <model> --num-gpus 1 --port 9000`
- Run all tests: `uv run tracr test`

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
- Do not persist raw API keys to metadata/output files.
- Local mode should degrade gracefully when GPUs/vLLM are unavailable.
- If same `job_id` is reused, append new runs with incremented `run_num`.

## Testing & Validation

- Add/adjust tests for behavior changes in orchestration, layout, and path discovery.
- For quick checks, run:
  - `python -m compileall -q tracr tests`
  - `uv run tracr test`
- Prefer deterministic tests with temporary directories for filesystem behavior.

## Agent Safety Rules

- Do not perform destructive git operations (e.g., `reset --hard`) unless explicitly requested.
- Do not modify unrelated files to satisfy formatting preferences.
- Treat `privasis/` as a reference project; changes there are usually out-of-scope.
