from __future__ import annotations

import asyncio
from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Select,
    Static,
    TextArea,
)

from tracr.core.provider_presets import DEFAULT_LOCAL_MODELS
from tracr.tui.common import DEFAULT_OCR_PROMPT, _row_key_value
from tracr.tui.service_client import ServiceClient, ServiceClientError


class LaunchWizardScreen(ModalScreen[dict[str, Any] | None]):
    CSS = """
    LaunchWizardScreen {
      align: center middle;
    }

    #wizard-root {
      width: 99%;
      height: 99%;
      border: heavy $accent;
      background: $panel;
      padding: 0 1;
    }

    #wizard-title {
      text-style: bold;
      color: $accent;
      height: auto;
      margin-top: 1;
    }

    #wizard-step {
      color: $text-muted;
      height: auto;
      margin-top: 1;
      margin-bottom: 0;
    }

    #wizard-body {
      height: 1fr;
      layout: horizontal;
      margin-top: 1;
    }

    #wizard-rail {
      width: 30;
      border: round $secondary;
      margin-right: 1;
      padding: 0 1;
    }

    #wizard-rail-title {
      text-style: bold;
      color: $accent;
      margin-top: 1;
      margin-bottom: 1;
    }

    #wizard-steps {
      height: 1fr;
    }

    #wizard-page-host {
      width: 1fr;
    }

    .wizard-page {
      height: 1fr;
      border: round $secondary;
      padding: 0 1;
    }

    .hidden {
      display: none;
    }

    .section-title {
      text-style: bold;
      color: $accent;
      margin-top: 1;
      margin-bottom: 1;
    }

    .help {
      color: $text-muted;
      margin-bottom: 1;
      height: auto;
    }

    .row {
      height: auto;
      margin-bottom: 1;
    }

    .label {
      width: 24;
      color: $text-muted;
    }

    #input-candidates {
      height: 14;
      margin-bottom: 1;
    }

    #job-config-candidates {
      height: 8;
      margin-bottom: 1;
    }

    #ocr-prompt {
      height: 14;
    }

    #local-model-panel {
      height: 7;
      margin-bottom: 1;
    }

    #local-model-library {
      height: 1fr;
    }

    #review-summary,
    #queued-models {
      height: 11;
      overflow: auto;
      margin-bottom: 1;
    }

    #wizard-nav {
      height: 3;
      align-horizontal: left;
      padding-top: 1;
    }

    #wizard-nav Button {
      margin-right: 1;
      min-width: 14;
    }
    """

    BINDINGS = [
        Binding("left", "prev_page", show=False),
        Binding("right", "next_page", show=False),
        Binding("ctrl+up", "focus_prev_page_widget", "Prev Field"),
        Binding("ctrl+down", "focus_next_page_widget", "Next Field"),
        Binding("ctrl+b", "prev_page", "Back"),
        Binding("ctrl+n", "next_page", "Next"),
        Binding("ctrl+l", "submit", "Launch"),
        Binding("ctrl+a", "add_models_to_queue", "Add Models"),
        Binding("space", "toggle_local_model", show=False),
        Binding("a", "select_all_local_models", show=False),
        Binding("x", "clear_local_model_selection", show=False),
        Binding("f5", "check_key", "Check Key"),
        Binding("escape", "cancel", "Cancel"),
    ]

    PAGE_TITLES = {
        "page-input": "Input Source",
        "page-job": "Job Metadata & Prompt",
        "page-mode": "Execution Mode",
        "page-api": "API Model Setup",
        "page-local": "Local Model Setup",
        "page-review": "Review & Launch",
    }

    ALL_PAGES = ("page-input", "page-job", "page-mode", "page-api", "page-local", "page-review")

    PAGE_FOCUS_ORDER: dict[str, list[str]] = {
        "page-input": [
            "input-candidates",
            "input-path",
            "job-config-candidates",
            "job-config-path",
            "load-job-config-btn",
            "refresh-job-configs-btn",
        ],
        "page-job": [
            "job-id",
            "job-title",
            "max-tokens",
            "temperature",
            "ocr-prompt",
        ],
        "page-mode": ["mode-radio"],
        "page-api": [
            "api-provider",
            "api-base-url",
            "api-key-env",
            "api-key",
            "api-models",
            "check-key-btn",
            "add-api-models-btn",
        ],
        "page-local": [
            "local-model-library",
            "add-local-models-btn",
            "local-custom-models",
            "local-tp-size",
            "local-dp-size",
            "local-gpu-mem",
            "local-max-len",
            "local-batch-size",
        ],
        "page-review": [
            "queued-models",
            "remove-queued-model-btn",
            "clear-queued-models-btn",
        ],
    }

    def __init__(
        self,
        *,
        client: ServiceClient,
        inputs_root: str,
        input_candidates: list[dict[str, Any]],
        job_configs_root: str,
        job_config_candidates: list[dict[str, Any]],
        presets: list[dict[str, Any]],
        local_models: list[str],
    ):
        super().__init__()
        self.client = client
        self.inputs_root = inputs_root
        self.input_candidates = input_candidates
        self.job_configs_root = job_configs_root
        self.job_config_candidates = job_config_candidates
        self.presets = presets
        self.local_models = local_models or list(DEFAULT_LOCAL_MODELS)

        self.current_step = 0
        self.model_queue: list[dict[str, Any]] = []
        self.selected_queue_index: int | None = None
        self.preset_by_key = {item["key"]: item for item in presets}
        self.local_selected_models: set[str] = set()
        self.local_highlighted_model: str | None = self.local_models[0] if self.local_models else None

    def compose(self) -> ComposeResult:
        preset_options = [(item["label"], item["key"]) for item in self.presets]
        if not preset_options:
            preset_options = [("Custom", "custom")]
        else:
            preset_options.append(("Custom", "custom"))

        with Container(id="wizard-root"):
            yield Label("TRACR Launch Wizard", id="wizard-title")
            yield Static(
                "Arrow flow: Left/Right steps, Up/Down inside tables, Enter selects, "
                "Ctrl+Up/Ctrl+Down jumps fields.",
                id="wizard-step",
            )

            with Horizontal(id="wizard-body"):
                with Vertical(id="wizard-rail"):
                    yield Label("Steps", id="wizard-rail-title")
                    yield DataTable(id="wizard-steps", cursor_type="row")
                with Vertical(id="wizard-page-host"):
                    with Vertical(id="page-input", classes="wizard-page"):
                        yield Label("Step: Input Source", classes="section-title")
                        yield Static(
                            "Use the tables with arrows; Enter copies the highlighted path.",
                            classes="help",
                        )
                        yield Static(f"Inputs root: {self.inputs_root}", classes="help")
                        yield DataTable(id="input-candidates", cursor_type="row")
                        with Horizontal(classes="row"):
                            yield Label("Selected input path", classes="label")
                            yield Input(id="input-path", placeholder="inputs/folder or /absolute/path")

                        yield Label("Job Config YAML (optional)", classes="section-title")
                        yield Static(f"Job configs root: {self.job_configs_root}", id="job-config-root", classes="help")
                        yield DataTable(id="job-config-candidates", cursor_type="row")
                        with Horizontal(classes="row"):
                            yield Label("Selected config path", classes="label")
                            yield Input(id="job-config-path", placeholder="job_configs/example.yaml")
                        with Horizontal(classes="row"):
                            yield Label("", classes="label")
                            yield Button("Load Config YAML", id="load-job-config-btn", variant="primary")
                            yield Button("Refresh Config List", id="refresh-job-configs-btn")

                    with Vertical(id="page-job", classes="wizard-page hidden"):
                        yield Label("Step: Job Metadata & Prompt", classes="section-title")
                        with Horizontal(classes="row"):
                            yield Label("Job id (optional)", classes="label")
                            yield Input(id="job-id", placeholder="comparison-batch")

                        with Horizontal(classes="row"):
                            yield Label("Job title (optional)", classes="label")
                            yield Input(id="job-title", placeholder="invoice-batch-20260206")

                        with Horizontal(classes="row"):
                            yield Label("Max tokens", classes="label")
                            yield Input(value="2048", id="max-tokens")

                        with Horizontal(classes="row"):
                            yield Label("Temperature", classes="label")
                            yield Input(value="0.0", id="temperature")

                        yield Label("OCR prompt", classes="section-title")
                        yield TextArea(DEFAULT_OCR_PROMPT, id="ocr-prompt")

                    with Vertical(id="page-mode", classes="wizard-page hidden"):
                        yield Label("Step: Execution Mode", classes="section-title")
                        yield Static(
                            "Choose a mode, then queue models. You can switch modes and add more.",
                            classes="help",
                        )
                        with RadioSet(id="mode-radio"):
                            yield RadioButton("API-based", id="mode-api", value=True)
                            yield RadioButton("Local vLLM", id="mode-local")

                    with Vertical(id="page-api", classes="wizard-page hidden"):
                        yield Label("Step: API Model Setup", classes="section-title")

                        with Horizontal(classes="row"):
                            yield Label("Provider preset", classes="label")
                            yield Select(options=preset_options, value=preset_options[0][1], id="api-provider")

                        with Horizontal(classes="row"):
                            yield Label("Endpoint URL", classes="label")
                            yield Input(id="api-base-url")

                        with Horizontal(classes="row"):
                            yield Label("API key env var", classes="label")
                            yield Input(id="api-key-env")

                        with Horizontal(classes="row"):
                            yield Label("API key override", classes="label")
                            yield Input(password=True, id="api-key", placeholder="optional")

                        with Horizontal(classes="row"):
                            yield Label("Model(s)", classes="label")
                            yield Input(id="api-models", placeholder="gpt-4.1-mini, openai/gpt-oss-120b")

                        with Horizontal(classes="row"):
                            yield Label("Example models", classes="label")
                            yield Static("No preset examples", id="api-model-examples")

                        with Horizontal(classes="row"):
                            yield Label("Key status", classes="label")
                            yield Static("Not checked", id="api-key-status")

                        with Horizontal(classes="row"):
                            yield Label("", classes="label")
                            yield Button("Check Key (F5)", id="check-key-btn")
                            yield Button("Add API Model(s) (^A)", id="add-api-models-btn", variant="success")

                    with Vertical(id="page-local", classes="wizard-page hidden"):
                        yield Label("Step: Local Model Setup", classes="section-title")
                        yield Static(
                            "Use the model library with arrows. Enter or Space toggles highlighted model.",
                            classes="help",
                        )

                        with Vertical(id="local-model-panel"):
                            yield DataTable(id="local-model-library", cursor_type="row")

                        with Horizontal(classes="row"):
                            yield Label("", classes="label")
                            yield Button("Add Local Model(s) (^A)", id="add-local-models-btn", variant="success")

                        with Horizontal(classes="row"):
                            yield Label("Custom model(s)", classes="label")
                            yield Input(id="local-custom-models", placeholder="org/model-a, org/model-b")

                        with Horizontal(classes="row"):
                            yield Label("Tensor parallel GPUs", classes="label")
                            yield Input(value="1", id="local-tp-size")

                        with Horizontal(classes="row"):
                            yield Label("Data parallel size", classes="label")
                            yield Input(value="1", id="local-dp-size")

                        with Horizontal(classes="row"):
                            yield Label("GPU memory utilization", classes="label")
                            yield Input(value="0.90", id="local-gpu-mem")

                        with Horizontal(classes="row"):
                            yield Label("Max model length", classes="label")
                            yield Input(id="local-max-len", placeholder="optional")

                        with Horizontal(classes="row"):
                            yield Label("Max concurrent requests", classes="label")
                            yield Input(value="8", id="local-batch-size")
                        yield Static("Controls in-flight OCR requests; progress updates are incremental as requests finish.", classes="help")

                    with Vertical(id="page-review", classes="wizard-page hidden"):
                        yield Label("Step: Review & Launch", classes="section-title")
                        yield Static("Queued models to run:", classes="help")
                        yield DataTable(id="queued-models", cursor_type="row")
                        with Horizontal(classes="row"):
                            yield Label("", classes="label")
                            yield Button("Remove Selected Model", id="remove-queued-model-btn", variant="warning")
                            yield Button("Clear Queue", id="clear-queued-models-btn", variant="error")
                        yield Static("", id="review-summary")

            with Horizontal(id="wizard-nav"):
                yield Button("Back (^B)", id="back-btn")
                yield Button("Next (^N)", id="next-btn", variant="primary")
                yield Button("Launch (^L)", id="launch-btn", variant="success")
                yield Button("Cancel (Esc)", id="cancel-btn", variant="error")

    async def on_mount(self) -> None:
        step_table = self.query_one("#wizard-steps", DataTable)
        step_table.add_columns("", "Step")

        input_table = self.query_one("#input-candidates", DataTable)
        input_table.add_columns("Kind", "Path")

        if self.input_candidates:
            for candidate in self.input_candidates:
                path = candidate.get("path", "")
                input_table.add_row(candidate.get("kind", ""), candidate.get("relative_to_inputs", path), key=path)
            self.query_one("#input-path", Input).value = self.input_candidates[0].get("path", "")
        else:
            input_table.add_row("info", "No entries found under inputs/; manual path required.")

        config_table = self.query_one("#job-config-candidates", DataTable)
        config_table.add_columns("Config file")
        self._render_job_config_candidates()

        queue_table = self.query_one("#queued-models", DataTable)
        queue_table.add_columns("#", "Mode", "Model", "Config")
        self._render_model_queue()

        local_table = self.query_one("#local-model-library", DataTable)
        local_table.add_columns("Use", "Model")
        self._render_local_model_library()

        provider = self.query_one("#api-provider", Select)
        await self._apply_preset(str(provider.value) if provider.value is not None else None)

        self._show_current_page(focus_default=True)
        input_table.focus()

    def _render_step_rail(self) -> None:
        step_table = self.query_one("#wizard-steps", DataTable)
        step_table.clear(columns=False)

        active_pages = self._active_pages()
        for index, page_id in enumerate(active_pages):
            marker = ">"
            if index < self.current_step:
                marker = "x"
            elif index > self.current_step:
                marker = "-"
            step_table.add_row(marker, self.PAGE_TITLES[page_id], key=page_id)

        try:
            step_table.move_cursor(row=self.current_step)
        except Exception:
            pass

    def _render_job_config_candidates(self) -> None:
        table = self.query_one("#job-config-candidates", DataTable)
        table.clear(columns=False)

        self.query_one("#job-config-root", Static).update(f"Job configs root: {self.job_configs_root}")
        if not self.job_config_candidates:
            table.add_row("No YAML configs found under job_configs/")
            return

        for candidate in self.job_config_candidates:
            path = str(candidate.get("path", ""))
            label = str(candidate.get("relative_to_configs", path))
            table.add_row(label, key=path)

        first_path = str(self.job_config_candidates[0].get("path", ""))
        if first_path and not self.query_one("#job-config-path", Input).value.strip():
            self.query_one("#job-config-path", Input).value = first_path

    def _render_local_model_library(self) -> None:
        table = self.query_one("#local-model-library", DataTable)
        table.clear(columns=False)

        if not self.local_models:
            self.local_highlighted_model = None
            table.add_row("-", "No local model defaults configured")
            return

        for model in self.local_models:
            marker = Text("[x]") if model in self.local_selected_models else Text("[ ]")
            table.add_row(marker, model, key=model)

        if self.local_highlighted_model not in self.local_models:
            self.local_highlighted_model = self.local_models[0]

        if self.local_highlighted_model is not None:
            try:
                row_index = table.get_row_index(self.local_highlighted_model)
                table.move_cursor(row=row_index)
            except Exception:
                self.local_highlighted_model = self.local_models[0]

    def _highlighted_local_model(self) -> str | None:
        if self.local_highlighted_model in self.local_models:
            return self.local_highlighted_model
        if self.local_models:
            return self.local_models[0]
        return None

    def _toggle_local_model_by_name(self, model: str) -> None:
        if model not in self.local_models:
            return
        if model in self.local_selected_models:
            self.local_selected_models.remove(model)
        else:
            self.local_selected_models.add(model)
        self.local_highlighted_model = model
        self._render_local_model_library()

    def _model_queue_key(self, model: dict[str, Any]) -> tuple[Any, ...]:
        mode = str(model.get("mode", ""))
        if mode == "api":
            return (
                "api",
                model.get("model"),
                model.get("provider"),
                model.get("base_url"),
                model.get("api_key_env"),
                model.get("api_key"),
            )
        return (
            "local",
            model.get("model"),
            model.get("tensor_parallel_size"),
            model.get("data_parallel_size"),
            model.get("gpu_memory_utilization"),
            model.get("max_model_len"),
            model.get("max_concurrent_requests"),
            tuple(model.get("extra_vllm_args") or []),
        )

    def _render_model_queue(self) -> None:
        table = self.query_one("#queued-models", DataTable)
        table.clear(columns=False)

        if not self.model_queue:
            self.selected_queue_index = None
            table.add_row("·", "-", "(none)", "Add models from API or Local setup pages.")
            return

        for idx, model in enumerate(self.model_queue):
            mode = str(model.get("mode", ""))
            if mode == "api":
                config = f"{model.get('provider') or 'custom'} @ {model.get('base_url')}"
            else:
                config = (
                    f"tp={model.get('tensor_parallel_size')} "
                    f"dp={model.get('data_parallel_size')} "
                    f"gpu_mem={model.get('gpu_memory_utilization')} "
                    f"max_len={model.get('max_model_len')} "
                    f"concurrency={model.get('max_concurrent_requests')}"
                )

            table.add_row(
                str(idx + 1),
                mode,
                str(model.get("model", "")),
                config,
                key=str(idx),
            )

        if self.selected_queue_index is None:
            self.selected_queue_index = 0

        try:
            table.move_cursor(row=self.selected_queue_index)
        except Exception:
            self.selected_queue_index = 0

    def _add_models_to_queue(self, models: list[dict[str, Any]]) -> tuple[int, int]:
        existing = {self._model_queue_key(model) for model in self.model_queue}
        added = 0
        duplicates = 0
        for model in models:
            key = self._model_queue_key(model)
            if key in existing:
                duplicates += 1
                continue
            existing.add(key)
            self.model_queue.append(model)
            added += 1

        self._render_model_queue()
        if self._current_page_id() == "page-review":
            self._render_review_summary()
        return added, duplicates

    def _active_pages(self) -> list[str]:
        mode_api = True
        try:
            mode_api = self.query_one("#mode-api", RadioButton).value
        except Exception:
            mode_api = True

        return [
            "page-input",
            "page-job",
            "page-mode",
            "page-api" if mode_api else "page-local",
            "page-review",
        ]

    def _current_page_id(self) -> str:
        pages = self._active_pages()
        self.current_step = max(0, min(self.current_step, len(pages) - 1))
        return pages[self.current_step]

    def _show_current_page(self, *, focus_default: bool = False) -> None:
        current = self._current_page_id()

        for page_id in self.ALL_PAGES:
            page = self.query_one(f"#{page_id}")
            if page_id == current:
                page.remove_class("hidden")
            else:
                page.add_class("hidden")

        step_widget = self.query_one("#wizard-step", Static)
        step_widget.update(
            f"Step {self.current_step + 1}/{len(self._active_pages())}: {self.PAGE_TITLES[current]} "
            "| Left/Right pages | Ctrl+Up/Down fields | Enter selects | ^A add models | ^L launch"
        )

        self._render_step_rail()
        self._update_nav_buttons()

        if current == "page-review":
            self._render_review_summary()
        if focus_default:
            self._focus_default_for_page(current)

    def _update_nav_buttons(self) -> None:
        current = self._current_page_id()
        back_btn = self.query_one("#back-btn", Button)
        next_btn = self.query_one("#next-btn", Button)
        launch_btn = self.query_one("#launch-btn", Button)

        back_btn.disabled = self.current_step == 0
        next_btn.disabled = current == "page-review"
        launch_btn.disabled = current != "page-review"

    def _focus_default_for_page(self, page_id: str) -> None:
        targets = self.PAGE_FOCUS_ORDER.get(page_id, [])
        for widget_id in targets:
            try:
                widget = self.query_one(f"#{widget_id}")
            except Exception:
                continue
            widget.focus()
            return

    def _focus_page_widget(self, direction: int) -> None:
        page_id = self._current_page_id()
        widget_ids = self.PAGE_FOCUS_ORDER.get(page_id, [])
        focusable: list[Widget] = []
        for widget_id in widget_ids:
            try:
                focusable.append(self.query_one(f"#{widget_id}"))
            except Exception:
                continue

        if not focusable:
            return

        focused = self.app.focused
        if focused is None:
            target_index = 0 if direction > 0 else len(focusable) - 1
            focusable[target_index].focus()
            return

        current_index = -1
        for idx, widget in enumerate(focusable):
            if widget is focused:
                current_index = idx
                break

        if current_index < 0:
            target_index = 0 if direction > 0 else len(focusable) - 1
        else:
            target_index = (current_index + direction) % len(focusable)
        focusable[target_index].focus()

    def _validate_api_form_for_add(self) -> bool:
        base_url = self.query_one("#api-base-url", Input).value.strip()
        models_raw = self.query_one("#api-models", Input).value.strip()
        if not base_url:
            self.notify("API endpoint URL is required", severity="error")
            self.query_one("#api-base-url", Input).focus()
            return False
        if not models_raw:
            self.notify("At least one API model is required", severity="error")
            self.query_one("#api-models", Input).focus()
            return False
        return True

    def _validate_local_form_for_add(self) -> bool:
        if not self._collect_local_model_names():
            self.notify("Select at least one local model", severity="error")
            self.query_one("#local-model-library", DataTable).focus()
            return False

        try:
            tp_size = int(self.query_one("#local-tp-size", Input).value.strip())
            if tp_size <= 0:
                raise ValueError
        except Exception:
            self.notify("Tensor parallel GPUs must be a positive integer", severity="error")
            self.query_one("#local-tp-size", Input).focus()
            return False

        try:
            dp_size = int(self.query_one("#local-dp-size", Input).value.strip())
            if dp_size <= 0:
                raise ValueError
        except Exception:
            self.notify("Data parallel size must be a positive integer", severity="error")
            self.query_one("#local-dp-size", Input).focus()
            return False

        try:
            gpu_mem = float(self.query_one("#local-gpu-mem", Input).value.strip())
            if gpu_mem <= 0.0 or gpu_mem > 1.0:
                raise ValueError
        except Exception:
            self.notify("GPU memory utilization must be in (0.0, 1.0]", severity="error")
            self.query_one("#local-gpu-mem", Input).focus()
            return False

        max_len_raw = self.query_one("#local-max-len", Input).value.strip()
        if max_len_raw:
            try:
                max_len = int(max_len_raw)
                if max_len <= 0:
                    raise ValueError
            except Exception:
                self.notify("Max model length must be a positive integer when set", severity="error")
                self.query_one("#local-max-len", Input).focus()
                return False

        try:
            batch_size = int(self.query_one("#local-batch-size", Input).value.strip())
            if batch_size <= 0:
                raise ValueError
        except Exception:
            self.notify("Max concurrent requests must be a positive integer", severity="error")
            self.query_one("#local-batch-size", Input).focus()
            return False

        return True

    def _validate_page(self, page_id: str) -> bool:
        if page_id == "page-input":
            input_path = self.query_one("#input-path", Input).value.strip()
            if not input_path:
                self.notify("Input path is required", severity="error")
                self.query_one("#input-path", Input).focus()
                return False
            return True

        if page_id == "page-job":
            job_id_value = self.query_one("#job-id", Input).value.strip()
            if "/" in job_id_value or "\\" in job_id_value:
                self.notify("Job id cannot contain path separators", severity="error")
                self.query_one("#job-id", Input).focus()
                return False

            try:
                max_tokens = int(self.query_one("#max-tokens", Input).value.strip())
                if max_tokens <= 0:
                    raise ValueError
            except Exception:
                self.notify("Max tokens must be a positive integer", severity="error")
                self.query_one("#max-tokens", Input).focus()
                return False

            try:
                temperature = float(self.query_one("#temperature", Input).value.strip())
                if temperature < 0.0 or temperature > 2.0:
                    raise ValueError
            except Exception:
                self.notify("Temperature must be a number in [0.0, 2.0]", severity="error")
                self.query_one("#temperature", Input).focus()
                return False
            return True

        if page_id == "page-api":
            if self.model_queue:
                return True
            if not self._validate_api_form_for_add():
                return False
            return True

        if page_id == "page-local":
            if self.model_queue:
                return True
            if not self._validate_local_form_for_add():
                return False
            return True

        return True

    def _collect_local_model_names(self) -> list[str]:
        selected: list[str] = [model for model in self.local_models if model in self.local_selected_models]

        custom_raw = self.query_one("#local-custom-models", Input).value
        custom_models = [entry.strip() for entry in custom_raw.replace("\n", ",").split(",") if entry.strip()]
        selected.extend(custom_models)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in selected:
            if item not in seen:
                deduped.append(item)
                seen.add(item)

        return deduped

    def _collect_models_api(self) -> list[dict[str, Any]]:
        provider = str(self.query_one("#api-provider", Select).value)
        models_raw = self.query_one("#api-models", Input).value
        base_url = self.query_one("#api-base-url", Input).value.strip()
        api_key_env = self.query_one("#api-key-env", Input).value.strip()
        api_key = self.query_one("#api-key", Input).value.strip()

        model_names = [entry.strip() for entry in models_raw.replace("\n", ",").split(",") if entry.strip()]

        return [
            {
                "model": model,
                "mode": "api",
                "provider": provider if provider != "custom" else None,
                "base_url": base_url,
                "api_key_env": api_key_env or None,
                "api_key": api_key or None,
            }
            for model in model_names
        ]

    def _collect_models_local(self) -> list[dict[str, Any]]:
        models = self._collect_local_model_names()
        tp_size = int(self.query_one("#local-tp-size", Input).value.strip() or "1")
        dp_size = int(self.query_one("#local-dp-size", Input).value.strip() or "1")
        gpu_mem = float(self.query_one("#local-gpu-mem", Input).value.strip() or "0.90")
        max_len_raw = self.query_one("#local-max-len", Input).value.strip()
        max_len = int(max_len_raw) if max_len_raw else None
        batch_size = int(self.query_one("#local-batch-size", Input).value.strip() or "8")

        return [
            {
                "model": model,
                "mode": "local",
                "tensor_parallel_size": tp_size,
                "data_parallel_size": dp_size,
                "gpu_memory_utilization": gpu_mem,
                "max_model_len": max_len,
                "max_concurrent_requests": batch_size,
            }
            for model in models
        ]

    def _build_payload(self) -> dict[str, Any]:
        job_id = self.query_one("#job-id", Input).value.strip()
        title = self.query_one("#job-title", Input).value.strip()
        input_path = self.query_one("#input-path", Input).value.strip()
        prompt = self.query_one("#ocr-prompt", TextArea).text
        max_tokens = int(self.query_one("#max-tokens", Input).value.strip())
        temperature = float(self.query_one("#temperature", Input).value.strip())

        if self.model_queue:
            models = [dict(model) for model in self.model_queue]
        else:
            mode_is_api = self.query_one("#mode-api", RadioButton).value
            models = self._collect_models_api() if mode_is_api else self._collect_models_local()

        return {
            "job_id": job_id or None,
            "title": title or None,
            "input_path": input_path,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "models": models,
        }

    def _render_review_summary(self) -> None:
        try:
            payload = self._build_payload()
        except Exception as exc:  # noqa: BLE001
            self.query_one("#review-summary", Static).update(f"Cannot render review: {exc}")
            return

        lines = [
            f"Input: {payload['input_path']}",
            f"Job id: {payload.get('job_id') or '(auto-generated with timestamp)'}",
            f"Job title: {payload.get('title') or '(auto)'}",
            f"Max tokens: {payload['max_tokens']}",
            f"Temperature: {payload['temperature']}",
            f"Prompt length: {len(payload['prompt'])} chars",
            f"Queued models: {len(payload['models'])}",
            "",
            "Models:",
        ]

        for model in payload["models"]:
            if model["mode"] == "api":
                key_state = "inline-key" if model.get("api_key") else f"env:{model.get('api_key_env') or '(unset)'}"
                lines.append(
                    f"- {model['model']} [api] provider={model.get('provider') or 'custom'} "
                    f"base_url={model.get('base_url')} key={key_state}"
                )
            else:
                lines.append(
                    f"- {model['model']} [local] tp={model.get('tensor_parallel_size')} "
                    f"dp={model.get('data_parallel_size')} "
                    f"gpu_mem={model.get('gpu_memory_utilization')} max_len={model.get('max_model_len')} "
                    f"concurrency={model.get('max_concurrent_requests')}"
                )

        lines.append("")
        lines.append("Press Ctrl+L (or Launch button) to submit.")
        self.query_one("#review-summary", Static).update("\n".join(lines))

    async def _apply_preset(self, provider_key: str | None) -> None:
        base_url = self.query_one("#api-base-url", Input)
        key_env = self.query_one("#api-key-env", Input)
        models_input = self.query_one("#api-models", Input)
        example_models = self.query_one("#api-model-examples", Static)

        if provider_key and provider_key in self.preset_by_key:
            preset = self.preset_by_key[provider_key]
            base_url.value = preset["base_url"]
            key_env.value = preset["api_key_env"]
            examples = [str(item).strip() for item in preset.get("example_models", []) if str(item).strip()]
            if examples:
                example_models.update(", ".join(examples))
                models_input.placeholder = ", ".join(examples)
            else:
                example_models.update("No preset examples")
                models_input.placeholder = "gpt-4.1-mini, openai/gpt-oss-120b"
            await self._update_key_status(provider_key, preset["api_key_env"])
        elif provider_key == "custom":
            self.query_one("#api-key-status", Static).update("Custom provider; set endpoint + key env/override")
            example_models.update("No preset examples")
            models_input.placeholder = "gpt-4.1-mini, openai/gpt-oss-120b"
        else:
            base_url.value = ""
            key_env.value = ""
            self.query_one("#api-key-status", Static).update("Not checked")
            example_models.update("No preset examples")
            models_input.placeholder = "gpt-4.1-mini, openai/gpt-oss-120b"

    async def _update_key_status(self, provider: str, api_key_env: str | None) -> None:
        status_widget = self.query_one("#api-key-status", Static)
        status_widget.update("Checking key...")

        def _request() -> dict[str, Any]:
            return self.client.provider_key_status(provider, api_key_env)

        try:
            result = await asyncio.to_thread(_request)
        except ServiceClientError as exc:
            status_widget.update(f"Error: {exc}")
            return

        present = result.get("present", False)
        env_name = result.get("api_key_env")
        status_widget.update(f"{'Found' if present else 'Missing'}: {env_name}")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _jump_to_step(self, target_index: int) -> None:
        pages = self._active_pages()
        if not pages:
            return

        target_index = max(0, min(target_index, len(pages) - 1))
        if target_index == self.current_step:
            return

        if target_index > self.current_step:
            for step in range(self.current_step, target_index):
                if not self._validate_page(pages[step]):
                    return

        self.current_step = target_index
        self._show_current_page(focus_default=True)

    def action_prev_page(self) -> None:
        if self.current_step <= 0:
            return
        self.current_step -= 1
        self._show_current_page(focus_default=True)

    def action_next_page(self) -> None:
        current = self._current_page_id()
        if not self._validate_page(current):
            return

        if current == "page-review":
            return

        self.current_step += 1
        self._show_current_page(focus_default=True)

    def action_focus_next_page_widget(self) -> None:
        self._focus_page_widget(1)

    def action_focus_prev_page_widget(self) -> None:
        self._focus_page_widget(-1)

    def action_toggle_local_model(self) -> None:
        if self._current_page_id() != "page-local":
            return
        model = self._highlighted_local_model()
        if model is None:
            return
        self._toggle_local_model_by_name(model)

    def action_select_all_local_models(self) -> None:
        if self._current_page_id() != "page-local":
            return
        self.local_selected_models = set(self.local_models)
        self._render_local_model_library()

    def action_clear_local_model_selection(self) -> None:
        if self._current_page_id() != "page-local":
            return
        self.local_selected_models.clear()
        self._render_local_model_library()

    async def action_check_key(self) -> None:
        provider = str(self.query_one("#api-provider", Select).value)
        key_env = self.query_one("#api-key-env", Input).value.strip() or None
        await self._update_key_status(provider, key_env)

    async def action_refresh_job_configs(self) -> None:
        try:
            payload = await asyncio.to_thread(self.client.list_job_configs)
        except ServiceClientError as exc:
            self.notify(f"Config refresh failed: {exc}", severity="error")
            return

        self.job_configs_root = str(payload.get("job_configs_root", self.job_configs_root))
        self.job_config_candidates = list(payload.get("candidates", []))
        self._render_job_config_candidates()
        self.notify("Job config list refreshed", severity="information")

    async def _apply_loaded_job_config(self, payload: dict[str, Any]) -> None:
        self.query_one("#input-path", Input).value = str(payload.get("input_path", "")).strip()
        self.query_one("#job-id", Input).value = str(payload.get("job_id", "") or "")
        self.query_one("#job-title", Input).value = str(payload.get("title", "") or "")
        self.query_one("#ocr-prompt", TextArea).text = str(payload.get("prompt", DEFAULT_OCR_PROMPT))
        self.query_one("#max-tokens", Input).value = str(payload.get("max_tokens", 2048))
        self.query_one("#temperature", Input).value = str(payload.get("temperature", 0.0))

        raw_models = payload.get("models", [])
        loaded_models: list[dict[str, Any]] = []
        for raw_model in raw_models:
            if not isinstance(raw_model, dict):
                continue
            mode = str(raw_model.get("mode", "")).strip().lower()
            model_name = str(raw_model.get("model", "")).strip()
            if mode not in {"api", "local"} or not model_name:
                continue

            if mode == "api":
                loaded_models.append(
                    {
                        "model": model_name,
                        "mode": "api",
                        "provider": raw_model.get("provider"),
                        "base_url": raw_model.get("base_url"),
                        "api_key_env": raw_model.get("api_key_env"),
                        "api_key": raw_model.get("api_key"),
                    }
                )
            else:
                raw_tp = raw_model.get("tensor_parallel_size", 1)
                raw_dp = raw_model.get("data_parallel_size", 1)
                raw_gpu_mem = raw_model.get("gpu_memory_utilization", 0.90)
                raw_max_concurrency = raw_model.get("max_concurrent_requests", 8)
                loaded_models.append(
                    {
                        "model": model_name,
                        "mode": "local",
                        "tensor_parallel_size": int(raw_tp) if raw_tp is not None else 1,
                        "data_parallel_size": int(raw_dp) if raw_dp is not None else 1,
                        "gpu_memory_utilization": float(raw_gpu_mem) if raw_gpu_mem is not None else 0.90,
                        "max_model_len": raw_model.get("max_model_len"),
                        "max_concurrent_requests": int(raw_max_concurrency) if raw_max_concurrency is not None else 8,
                        "extra_vllm_args": list(raw_model.get("extra_vllm_args") or []),
                    }
                )

        self.model_queue = loaded_models
        self.selected_queue_index = 0 if loaded_models else None
        self._render_model_queue()

        first_api = next((model for model in loaded_models if model.get("mode") == "api"), None)
        if first_api:
            provider_value = str(first_api.get("provider") or "custom")
            if provider_value not in self.preset_by_key:
                provider_value = "custom"
            self.query_one("#api-provider", Select).value = provider_value
            await self._apply_preset(provider_value)
            self.query_one("#api-base-url", Input).value = str(first_api.get("base_url") or "")
            self.query_one("#api-key-env", Input).value = str(first_api.get("api_key_env") or "")
            self.query_one("#api-key", Input).value = str(first_api.get("api_key") or "")
            api_model_names = [str(model.get("model")) for model in loaded_models if model.get("mode") == "api"]
            self.query_one("#api-models", Input).value = ", ".join(api_model_names)

        self.local_selected_models.clear()
        if self.local_models:
            self.local_highlighted_model = self.local_models[0]
        else:
            self.local_highlighted_model = None
        self.query_one("#local-custom-models", Input).value = ""

        first_local = next((model for model in loaded_models if model.get("mode") == "local"), None)
        if first_local:
            local_names = [str(model.get("model")) for model in loaded_models if model.get("mode") == "local"]
            self.local_selected_models = {name for name in local_names if name in self.local_models}
            self.local_highlighted_model = next(iter(self.local_selected_models), self.local_highlighted_model)
            if self.local_highlighted_model not in self.local_models and self.local_models:
                self.local_highlighted_model = self.local_models[0]
            custom_local = [name for name in local_names if name not in self.local_models]
            self.query_one("#local-custom-models", Input).value = ", ".join(custom_local)
            self.query_one("#local-tp-size", Input).value = str(first_local.get("tensor_parallel_size", 1))
            self.query_one("#local-dp-size", Input).value = str(first_local.get("data_parallel_size", 1))
            self.query_one("#local-gpu-mem", Input).value = str(first_local.get("gpu_memory_utilization", 0.90))
            max_len_value = first_local.get("max_model_len")
            self.query_one("#local-max-len", Input).value = "" if max_len_value is None else str(max_len_value)
            self.query_one("#local-batch-size", Input).value = str(first_local.get("max_concurrent_requests", 8))

        self._render_local_model_library()

        first_mode = str(loaded_models[0].get("mode", "")) if loaded_models else "api"
        self.query_one("#mode-api", RadioButton).value = first_mode == "api"
        self.query_one("#mode-local", RadioButton).value = first_mode == "local"

    async def action_load_job_config(self) -> None:
        config_path = self.query_one("#job-config-path", Input).value.strip()
        if not config_path:
            self.notify("Config path is required", severity="warning")
            return

        try:
            payload = await asyncio.to_thread(self.client.load_job_config, config_path)
        except ServiceClientError as exc:
            self.notify(f"Config load failed: {exc}", severity="error")
            return

        await self._apply_loaded_job_config(payload)
        self._render_review_summary()
        self.notify(f"Loaded config: {config_path}", severity="information")

    def action_add_models_to_queue(self) -> None:
        current = self._current_page_id()
        if current == "page-api":
            self.action_add_api_models()
            return
        if current == "page-local":
            self.action_add_local_models()
            return
        self.notify("Go to API or Local setup page to add models", severity="warning")

    def action_add_api_models(self) -> None:
        if not self._validate_api_form_for_add():
            return
        models = self._collect_models_api()
        added, duplicates = self._add_models_to_queue(models)
        if added:
            self.notify(f"Added {added} API model(s) to queue", severity="information")
        elif duplicates:
            self.notify("All selected API models are already in queue", severity="warning")

    def action_add_local_models(self) -> None:
        if not self._validate_local_form_for_add():
            return
        models = self._collect_models_local()
        added, duplicates = self._add_models_to_queue(models)
        if added:
            self.notify(f"Added {added} local model(s) to queue", severity="information")
        elif duplicates:
            self.notify("All selected local models are already in queue", severity="warning")

    def action_remove_selected_queued_model(self) -> None:
        if not self.model_queue:
            self.notify("Model queue is empty", severity="warning")
            return
        if self.selected_queue_index is None or self.selected_queue_index >= len(self.model_queue):
            self.selected_queue_index = len(self.model_queue) - 1

        removed = self.model_queue.pop(self.selected_queue_index)
        if not self.model_queue:
            self.selected_queue_index = None
        else:
            self.selected_queue_index = min(self.selected_queue_index, len(self.model_queue) - 1)
        self._render_model_queue()
        if self._current_page_id() == "page-review":
            self._render_review_summary()
        self.notify(f"Removed model from queue: {removed.get('model')}", severity="information")

    def action_clear_queued_models(self) -> None:
        self.model_queue.clear()
        self.selected_queue_index = None
        self._render_model_queue()
        if self._current_page_id() == "page-review":
            self._render_review_summary()
        self.notify("Cleared queued models", severity="warning")

    async def action_submit(self) -> None:
        # Move to review if user submits early, validating each intermediate page.
        while self._current_page_id() != "page-review":
            current = self._current_page_id()
            if not self._validate_page(current):
                return
            self.current_step += 1
            self._show_current_page()

        if not self._validate_page("page-review"):
            return

        try:
            payload = self._build_payload()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Invalid launch form: {exc}", severity="error")
            return

        if not payload["models"]:
            self.notify("Select at least one model", severity="error")
            return

        for model in payload["models"]:
            if model.get("mode") != "api":
                continue
            if model.get("api_key"):
                continue

            provider = model.get("provider") or "custom"
            api_key_env = model.get("api_key_env")
            try:
                status = await asyncio.to_thread(self.client.provider_key_status, provider, api_key_env)
            except ServiceClientError as exc:
                self.notify(f"Key check failed: {exc}", severity="error")
                return

            if not status.get("present"):
                env_name = status.get("api_key_env") or "(unset)"
                self.notify(
                    f"Missing API key in env ({env_name}). Provide override key or update .env.",
                    severity="error",
                )
                return

        self.dismiss(payload)

    @on(Button.Pressed, "#back-btn")
    def on_back_pressed(self) -> None:
        self.action_prev_page()

    @on(Button.Pressed, "#next-btn")
    def on_next_pressed(self) -> None:
        self.action_next_page()

    @on(Button.Pressed, "#cancel-btn")
    def on_cancel_pressed(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#launch-btn")
    async def on_launch_pressed(self) -> None:
        await self.action_submit()

    @on(Button.Pressed, "#check-key-btn")
    async def on_check_key_pressed(self) -> None:
        await self.action_check_key()

    @on(Button.Pressed, "#load-job-config-btn")
    async def on_load_job_config_pressed(self) -> None:
        await self.action_load_job_config()

    @on(Button.Pressed, "#refresh-job-configs-btn")
    async def on_refresh_job_configs_pressed(self) -> None:
        await self.action_refresh_job_configs()

    @on(Button.Pressed, "#add-api-models-btn")
    def on_add_api_models_pressed(self) -> None:
        self.action_add_api_models()

    @on(Button.Pressed, "#add-local-models-btn")
    def on_add_local_models_pressed(self) -> None:
        self.action_add_local_models()

    @on(Button.Pressed, "#remove-queued-model-btn")
    def on_remove_queued_model_pressed(self) -> None:
        self.action_remove_selected_queued_model()

    @on(Button.Pressed, "#clear-queued-models-btn")
    def on_clear_queued_models_pressed(self) -> None:
        self.action_clear_queued_models()

    @on(DataTable.RowSelected, "#input-candidates")
    def on_input_candidate_selected(self, event: DataTable.RowSelected) -> None:
        key = _row_key_value(event.row_key)
        if key:
            self.query_one("#input-path", Input).value = key

    @on(DataTable.RowHighlighted, "#input-candidates")
    def on_input_candidate_highlighted(self, event: DataTable.RowHighlighted) -> None:
        key = _row_key_value(event.row_key)
        if key:
            self.query_one("#input-path", Input).value = key

    @on(DataTable.RowSelected, "#job-config-candidates")
    def on_job_config_candidate_selected(self, event: DataTable.RowSelected) -> None:
        key = _row_key_value(event.row_key)
        if key:
            self.query_one("#job-config-path", Input).value = key

    @on(DataTable.RowHighlighted, "#job-config-candidates")
    def on_job_config_candidate_highlighted(self, event: DataTable.RowHighlighted) -> None:
        key = _row_key_value(event.row_key)
        if key:
            self.query_one("#job-config-path", Input).value = key

    @on(DataTable.RowSelected, "#wizard-steps")
    def on_wizard_step_selected(self, event: DataTable.RowSelected) -> None:
        key = _row_key_value(event.row_key)
        if not key:
            return
        pages = self._active_pages()
        if key not in pages:
            return
        self._jump_to_step(pages.index(key))

    @on(DataTable.RowHighlighted, "#local-model-library")
    def on_local_model_highlighted(self, event: DataTable.RowHighlighted) -> None:
        key = _row_key_value(event.row_key)
        if key:
            self.local_highlighted_model = key

    @on(DataTable.RowSelected, "#local-model-library")
    def on_local_model_selected(self, event: DataTable.RowSelected) -> None:
        key = _row_key_value(event.row_key)
        if not key:
            return
        self.local_highlighted_model = key
        self._toggle_local_model_by_name(key)

    @on(DataTable.RowHighlighted, "#queued-models")
    def on_queued_model_highlighted(self, event: DataTable.RowHighlighted) -> None:
        key = _row_key_value(event.row_key)
        if not key or not key.isdigit():
            return
        self.selected_queue_index = int(key)

    @on(DataTable.RowSelected, "#queued-models")
    def on_queued_model_selected(self, event: DataTable.RowSelected) -> None:
        key = _row_key_value(event.row_key)
        if not key or not key.isdigit():
            return
        self.selected_queue_index = int(key)

    @on(Select.Changed, "#api-provider")
    async def on_provider_changed(self, event: Select.Changed) -> None:
        provider_value = str(event.value) if event.value is not None else None
        await self._apply_preset(provider_value)

    @on(RadioSet.Changed, "#mode-radio")
    def on_mode_changed(self, _: RadioSet.Changed) -> None:
        self.current_step = min(self.current_step, len(self._active_pages()) - 1)
        self._show_current_page(focus_default=True)
