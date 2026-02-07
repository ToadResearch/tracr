from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from tracr.core.provider_presets import DEFAULT_LOCAL_MODELS
from tracr.tui.common import _format_seconds, _progress_bar, _row_key_value, _token_usage_from_stats
from tracr.tui.screens import JobRunsScreen, LaunchWizardScreen, OutputViewerScreen, OutputsBrowserScreen
from tracr.tui.service_client import ServiceClient, ServiceClientError


class TracrTUIApp(App[None]):
    CSS = """
    Screen {
      layout: vertical;
    }

    #root {
      layout: horizontal;
      height: 1fr;
    }

    #jobs-pane {
      width: 2fr;
      border: solid $accent;
      margin: 0 1 1 1;
      padding: 0 1;
    }

    #details-pane {
      width: 1fr;
      border: solid $accent;
      margin: 0 1 1 0;
      padding: 0 1;
    }

    .pane-title {
      text-style: bold;
      color: $accent;
      height: auto;
      margin-top: 1;
    }

    #jobs-table {
      height: 1fr;
      margin-top: 1;
    }

    #job-actions {
      height: 3;
      align-horizontal: left;
      padding-top: 1;
    }

    #job-actions Button {
      margin-right: 1;
      min-width: 14;
    }

    #job-details,
    #gpu-details {
      height: 1fr;
      border: solid $secondary;
      padding: 0 1;
      margin-top: 1;
      margin-bottom: 1;
      overflow: auto;
    }
    """

    BINDINGS = [
        Binding("n", "new_job", "New Job"),
        Binding("enter", "open_selected_job", "Open Job"),
        Binding("m", "open_selected_job", "Open Job"),
        Binding("v", "view_selected_outputs", "View Pages"),
        Binding("o", "browse_outputs", "Browse Outputs"),
        Binding("d", "dismiss_selected", "Dismiss Done/Canceled"),
        Binding("r", "manual_refresh", "Refresh"),
        Binding("c", "cancel_selected", "Cancel Job"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, api_base_url: str):
        super().__init__()
        self.client = ServiceClient(api_base_url)
        self.jobs: list[dict[str, Any]] = []
        self.selected_job_id: str | None = None
        self.inputs_root: str = "inputs"
        self.input_candidates: list[dict[str, Any]] = []
        self.job_configs_root: str = "job_configs"
        self.job_config_candidates: list[dict[str, Any]] = []
        self.presets: list[dict[str, Any]] = []
        self.local_models: list[str] = list(DEFAULT_LOCAL_MODELS)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="root"):
            with Vertical(id="jobs-pane"):
                yield Label("Jobs", classes="pane-title")
                yield DataTable(id="jobs-table", cursor_type="row")
                with Horizontal(id="job-actions"):
                    yield Button("New Job (N)", id="new-job", variant="success")
                    yield Button("Open Job (Enter)", id="open-job", variant="primary")
                    yield Button("View Pages (V)", id="view-pages")
                    yield Button("Browse Outputs (O)", id="browse-outputs")
                    yield Button("Dismiss Done/Canceled (D)", id="dismiss-job")
                    yield Button("Refresh (R)", id="refresh")
                    yield Button("Cancel (C)", id="cancel-job", variant="warning")
                    yield Button("Quit (Q)", id="quit", variant="error")
            with Vertical(id="details-pane"):
                yield Label("Job Detail", classes="pane-title")
                yield Static("No job selected", id="job-details")
                yield Label("GPU", classes="pane-title")
                yield Static("No GPU data", id="gpu-details")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#jobs-table", DataTable)
        table.add_columns("Job", "Status", "Progress", "Runtime", "ETA", "OutTok", "Models")

        try:
            health = await asyncio.to_thread(self.client.health)
            self.sub_title = f"API {health.get('status', 'unknown')}"
        except ServiceClientError as exc:
            self.sub_title = f"API unavailable: {exc}"

        await self._refresh_static_setup()
        await self.refresh_all()
        self.set_interval(1.0, self._tick_refresh)

    async def _refresh_static_setup(self) -> None:
        try:
            inputs_payload = await asyncio.to_thread(self.client.list_inputs)
            self.inputs_root = inputs_payload.get("inputs_root", self.inputs_root)
            self.input_candidates = inputs_payload.get("candidates", [])
        except ServiceClientError:
            pass

        try:
            job_configs_payload = await asyncio.to_thread(self.client.list_job_configs)
            self.job_configs_root = job_configs_payload.get("job_configs_root", self.job_configs_root)
            self.job_config_candidates = job_configs_payload.get("candidates", [])
        except ServiceClientError:
            self.job_config_candidates = []

        try:
            self.presets = await asyncio.to_thread(self.client.list_presets)
        except ServiceClientError:
            self.presets = []

        try:
            self.local_models = await asyncio.to_thread(self.client.list_default_local_models)
        except ServiceClientError:
            self.local_models = list(DEFAULT_LOCAL_MODELS)

    async def _tick_refresh(self) -> None:
        await self.refresh_all(silent=True)

    async def refresh_all(self, silent: bool = False) -> None:
        try:
            jobs_payload, gpu_payload = await asyncio.gather(
                asyncio.to_thread(self.client.list_jobs),
                asyncio.to_thread(self.client.gpu_stats),
            )
        except ServiceClientError as exc:
            if not silent:
                self.notify(f"Refresh failed: {exc}", severity="error")
            return

        self.jobs = jobs_payload.get("jobs", [])
        self._render_jobs_table()
        self._render_gpu_payload(gpu_payload)

    def _render_jobs_table(self) -> None:
        table = self.query_one("#jobs-table", DataTable)
        table.clear(columns=False)

        for job in self.jobs:
            ratio = 0.0
            total = job.get("total_pages_all_models", 0)
            complete = job.get("completed_pages_all_models", 0)
            if total > 0:
                ratio = complete / total

            runtime = _format_seconds(job.get("runtime_seconds"))
            eta = _format_seconds(job.get("eta_seconds"))
            _, output_tokens, _ = _token_usage_from_stats(job.get("statistics"))

            table.add_row(
                job.get("job_id", ""),
                str(job.get("status", "")).upper(),
                _progress_bar(ratio),
                runtime,
                eta,
                str(output_tokens),
                str(len(job.get("models", []))),
                key=job.get("job_id", ""),
            )

        if self.selected_job_id:
            try:
                row_index = table.get_row_index(self.selected_job_id)
                table.move_cursor(row=row_index)
            except Exception:
                pass

        self._render_selected_job_details()

    def _render_selected_job_details(self) -> None:
        details = self.query_one("#job-details", Static)
        if not self.selected_job_id:
            details.update("No job selected")
            return

        job = next((item for item in self.jobs if item.get("job_id") == self.selected_job_id), None)
        if not job:
            details.update("Selected job no longer available")
            return

        job_in_tokens, job_out_tokens, job_total_tokens = _token_usage_from_stats(job.get("statistics"))
        lines = [
            f"Job: {job.get('job_id')}",
            f"Title: {job.get('title')}",
            f"Status: {str(job.get('status', '')).upper()}",
            f"Input: {job.get('input_path')}",
            f"Runtime: {_format_seconds(job.get('runtime_seconds'))}",
            f"ETA: {_format_seconds(job.get('eta_seconds'))}",
            f"Pages: {job.get('completed_pages_all_models')}/{job.get('total_pages_all_models')}",
            f"Tokens: in={job_in_tokens} out={job_out_tokens} total={job_total_tokens}",
            "Actions: Enter/M open job, V pages, O outputs, D dismiss done/canceled, C cancel, R refresh",
            "",
            "Runs:",
        ]

        for run in job.get("models", []):
            ratio = 0.0
            if run.get("total_pages", 0) > 0:
                ratio = run.get("completed_pages", 0) / run.get("total_pages", 0)
            lines.append(
                f"- {run.get('model')} [{run.get('mode')}]: {str(run.get('status', '')).upper()} "
                f"{run.get('completed_pages')}/{run.get('total_pages')} {_progress_bar(ratio, width=10)}"
            )
            run_in_tokens, run_out_tokens, run_total_tokens = _token_usage_from_stats(run.get("statistics"))
            lines.append(f"  tokens: in={run_in_tokens} out={run_out_tokens} total={run_total_tokens}")
            if run.get("current_pdf"):
                lines.append(f"  current: {Path(run['current_pdf']).name} p{run.get('current_page')}")
            if run.get("error"):
                lines.append(f"  error: {run['error']}")

        details.update("\n".join(lines))

    def _render_gpu_payload(self, payload: dict[str, Any]) -> None:
        details = self.query_one("#gpu-details", Static)
        gpus = payload.get("gpus", [])
        if not gpus:
            details.update("No NVIDIA GPU data available")
            return

        lines = [f"GPU count: {payload.get('gpu_count', len(gpus))}", ""]
        for item in gpus:
            lines.append(
                f"GPU {item['index']} {item['name']}: util {item['utilization_percent']}% "
                f"mem {item['memory_used_mb']}/{item['memory_total_mb']} MB"
            )
        details.update("\n".join(lines))

    @on(DataTable.RowHighlighted, "#jobs-table")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        job_id = _row_key_value(event.row_key)
        if not job_id:
            return
        self.selected_job_id = job_id
        self._render_selected_job_details()

    @on(DataTable.RowSelected, "#jobs-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        job_id = _row_key_value(event.row_key)
        if not job_id:
            return
        self.selected_job_id = job_id
        self._render_selected_job_details()

    @on(Button.Pressed, "#refresh")
    async def on_refresh_pressed(self) -> None:
        await self.refresh_all()

    async def action_manual_refresh(self) -> None:
        await self.refresh_all()

    @on(Button.Pressed, "#new-job")
    def on_new_job_pressed(self) -> None:
        self.action_new_job()

    @on(Button.Pressed, "#open-job")
    def on_open_job_pressed(self) -> None:
        self.action_open_selected_job()

    @on(Button.Pressed, "#view-pages")
    def on_view_pages_pressed(self) -> None:
        self.action_view_selected_outputs()

    @on(Button.Pressed, "#browse-outputs")
    def on_browse_outputs_pressed(self) -> None:
        self.action_browse_outputs()

    @on(Button.Pressed, "#dismiss-job")
    async def on_dismiss_job_pressed(self) -> None:
        await self.action_dismiss_selected()

    def action_new_job(self) -> None:
        self.run_worker(self._new_job_flow(), group="launch-job", exclusive=True)

    def action_open_selected_job(self) -> None:
        if not self.selected_job_id:
            self.notify("Select a job first", severity="warning")
            return
        self.push_screen(JobRunsScreen(client=self.client, job_id=self.selected_job_id))

    def action_view_selected_outputs(self) -> None:
        if not self.selected_job_id:
            self.notify("Select a job first", severity="warning")
            return
        self.push_screen(OutputViewerScreen(client=self.client, job_id=self.selected_job_id))

    def action_browse_outputs(self) -> None:
        self.push_screen(OutputsBrowserScreen(client=self.client))

    async def action_dismiss_selected(self) -> None:
        if not self.selected_job_id:
            self.notify("Select a completed or canceled job first", severity="warning")
            return

        selected_job = next((item for item in self.jobs if item.get("job_id") == self.selected_job_id), None)
        if not selected_job:
            self.notify("Selected job not found", severity="warning")
            return

        status = str(selected_job.get("status", "")).upper()
        if status not in {"COMPLETED", "CANCELED", "CANCELLED"}:
            self.notify("Only completed or canceled jobs can be dismissed from home view", severity="warning")
            return

        try:
            await asyncio.to_thread(self.client.dismiss_job, self.selected_job_id)
        except ServiceClientError as exc:
            self.notify(f"Dismiss failed: {exc}", severity="error")
            return

        dismissed_job_id = self.selected_job_id
        self.selected_job_id = None
        self.notify(f"Dismissed job: {dismissed_job_id}", severity="information")
        await self.refresh_all()

    async def _new_job_flow(self) -> None:
        await self._refresh_static_setup()

        wizard = LaunchWizardScreen(
            client=self.client,
            inputs_root=self.inputs_root,
            input_candidates=self.input_candidates,
            job_configs_root=self.job_configs_root,
            job_config_candidates=self.job_config_candidates,
            presets=self.presets,
            local_models=self.local_models,
        )

        payload = await self.push_screen_wait(wizard)
        if not payload:
            return

        try:
            result = await asyncio.to_thread(self.client.launch_job, payload)
        except ServiceClientError as exc:
            self.notify(f"Launch failed: {exc}", severity="error")
            return

        job = result.get("job", {})
        self.selected_job_id = job.get("job_id")
        self.notify(f"Launched job: {self.selected_job_id}", severity="information")
        await self.refresh_all()

    @on(Button.Pressed, "#cancel-job")
    async def on_cancel_pressed(self) -> None:
        await self.action_cancel_selected()

    async def action_cancel_selected(self) -> None:
        if not self.selected_job_id:
            self.notify("Select a job first", severity="warning")
            return

        try:
            await asyncio.to_thread(self.client.cancel_job, self.selected_job_id)
            self.notify(f"Canceled job: {self.selected_job_id}", severity="warning")
        except ServiceClientError as exc:
            self.notify(f"Cancel failed: {exc}", severity="error")
            return

        await self.refresh_all()

    @on(Button.Pressed, "#quit")
    def on_quit_pressed(self) -> None:
        self.exit()


def run_tui(api_base_url: str) -> None:
    app = TracrTUIApp(api_base_url=api_base_url)
    app.run()
