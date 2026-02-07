from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from tracr.tui.common import _format_seconds, _progress_bar, _row_key_value, _token_usage_from_stats
from tracr.tui.screens.output_viewer import OutputViewerScreen
from tracr.tui.service_client import ServiceClient, ServiceClientError


class JobRunsScreen(ModalScreen[None]):
    CSS = """
    JobRunsScreen {
      align: center middle;
    }

    #runs-root {
      width: 98%;
      height: 98%;
      border: heavy $accent;
      background: $panel;
      padding: 0 1;
    }

    #runs-title {
      text-style: bold;
      color: $accent;
      height: auto;
      margin-top: 1;
    }

    #runs-subtitle {
      color: $text-muted;
      height: auto;
      margin-bottom: 1;
    }

    #runs-body {
      height: 1fr;
      layout: horizontal;
    }

    #runs-table {
      width: 56%;
      margin-right: 1;
    }

    #runs-right {
      width: 44%;
      layout: vertical;
    }

    #runs-job-detail,
    #runs-gpu-detail {
      border: round $secondary;
      padding: 0 1;
      margin-bottom: 1;
      overflow: auto;
    }

    #runs-job-detail {
      height: 1fr;
    }

    #runs-gpu-detail {
      height: 12;
      margin-bottom: 0;
    }

    #runs-actions {
      height: 3;
      align-horizontal: left;
      padding-top: 1;
    }

    #runs-actions Button {
      margin-right: 1;
      min-width: 14;
    }
    """

    BINDINGS = [
        Binding("enter", "view_pages", "View Pages"),
        Binding("v", "view_pages", "View Pages"),
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "close", "Close"),
    ]

    def __init__(self, *, client: ServiceClient, job_id: str):
        super().__init__()
        self.client = client
        self.job_id = job_id
        self.job: dict[str, Any] | None = None
        self.gpu_payload: dict[str, Any] = {}
        self.selected_run_id: str | None = None

    def compose(self) -> ComposeResult:
        with Container(id="runs-root"):
            yield Label(f"TRACR Job Monitor - {self.job_id}", id="runs-title")
            yield Static("Per-model progress view. Enter/V opens page viewer.", id="runs-subtitle")
            with Horizontal(id="runs-body"):
                yield DataTable(id="runs-table", cursor_type="row")
                with Vertical(id="runs-right"):
                    yield Static("Loading job details...", id="runs-job-detail", markup=False)
                    yield Static("Loading GPU details...", id="runs-gpu-detail", markup=False)
            with Horizontal(id="runs-actions"):
                yield Button("View Pages (Enter)", id="runs-view-pages", variant="primary")
                yield Button("Refresh (R)", id="runs-refresh")
                yield Button("Close (Esc)", id="runs-close", variant="error")

    async def on_mount(self) -> None:
        table = self.query_one("#runs-table", DataTable)
        table.add_columns("Model", "Mode", "Status", "Progress", "Runtime", "ETA", "OutTok")
        await self.action_refresh()
        self.set_interval(1.0, self._tick_refresh)
        self.set_focus(table)

    async def _tick_refresh(self) -> None:
        await self.action_refresh(silent=True)

    async def action_refresh(self, silent: bool = False) -> None:
        try:
            job_payload, gpu_payload = await asyncio.gather(
                asyncio.to_thread(self.client.get_job, self.job_id),
                asyncio.to_thread(self.client.gpu_stats),
            )
        except ServiceClientError as exc:
            if not silent:
                self.notify(f"Refresh failed: {exc}", severity="error")
            return

        self.job = job_payload
        self.gpu_payload = gpu_payload
        self._render_runs_table()
        self._render_job_detail()
        self._render_gpu_detail()

    def _render_runs_table(self) -> None:
        table = self.query_one("#runs-table", DataTable)
        table.clear(columns=False)

        if not self.job:
            table.add_row("(no data)", "-", "-", "-", "-", "-", "-")
            return

        runs = self.job.get("models", [])
        if not runs:
            self.selected_run_id = None
            table.add_row("(no models)", "-", "-", "-", "-", "-", "-")
            return

        for run in runs:
            ratio = 0.0
            if run.get("total_pages", 0) > 0:
                ratio = run.get("completed_pages", 0) / run.get("total_pages", 0)
            _, output_tokens, _ = _token_usage_from_stats(run.get("statistics"))
            table.add_row(
                str(run.get("model", "")),
                str(run.get("mode", "")),
                str(run.get("status", "")).upper(),
                _progress_bar(ratio, width=10),
                _format_seconds(run.get("runtime_seconds")),
                _format_seconds(run.get("eta_seconds")),
                str(output_tokens),
                key=str(run.get("run_id", "")),
            )

        if self.selected_run_id is None:
            self.selected_run_id = str(runs[0].get("run_id", ""))

        try:
            row_index = table.get_row_index(self.selected_run_id)
            table.move_cursor(row=row_index)
        except Exception:
            self.selected_run_id = str(runs[0].get("run_id", ""))

    def _render_job_detail(self) -> None:
        widget = self.query_one("#runs-job-detail", Static)
        if not self.job:
            widget.update("No job data available.")
            return

        stats = self.job.get("statistics", {})
        in_tokens, out_tokens, total_tokens = _token_usage_from_stats(stats)

        lines = [
            f"Job: {self.job.get('job_id')}",
            f"Title: {self.job.get('title')}",
            f"Status: {str(self.job.get('status', '')).upper()}",
            f"Input: {self.job.get('input_path')}",
            f"Runtime: {_format_seconds(self.job.get('runtime_seconds'))}",
            f"ETA: {_format_seconds(self.job.get('eta_seconds'))}",
            f"Pages: {self.job.get('completed_pages_all_models')}/{self.job.get('total_pages_all_models')}",
            f"Tokens (aggregate): in={in_tokens} out={out_tokens} total={total_tokens}",
            "",
        ]

        runs = self.job.get("models", [])
        selected_run = None
        for run in runs:
            if str(run.get("run_id", "")) == str(self.selected_run_id):
                selected_run = run
                break

        if not selected_run:
            lines.append("Select a model run to view details.")
            widget.update("\n".join(lines))
            return

        run_stats = selected_run.get("statistics", {})
        run_in_tokens, run_out_tokens, run_total_tokens = _token_usage_from_stats(run_stats)
        ratio = 0.0
        if selected_run.get("total_pages", 0) > 0:
            ratio = selected_run.get("completed_pages", 0) / selected_run.get("total_pages", 0)

        lines.extend(
            [
                f"Selected Model: {selected_run.get('model')}",
                f"Mode: {selected_run.get('mode')}",
                f"Run status: {str(selected_run.get('status', '')).upper()}",
                f"Run progress: {selected_run.get('completed_pages')}/{selected_run.get('total_pages')} {_progress_bar(ratio, width=14)}",
                f"Run runtime: {_format_seconds(selected_run.get('runtime_seconds'))}",
                f"Run ETA: {_format_seconds(selected_run.get('eta_seconds'))}",
                f"Run tokens: in={run_in_tokens} out={run_out_tokens} total={run_total_tokens}",
            ]
        )
        if selected_run.get("current_pdf"):
            lines.append(
                f"Current: {Path(str(selected_run.get('current_pdf'))).name} p{selected_run.get('current_page')}"
            )
        if selected_run.get("error"):
            lines.append(f"Error: {selected_run.get('error')}")

        widget.update("\n".join(lines))

    def _render_gpu_detail(self) -> None:
        details = self.query_one("#runs-gpu-detail", Static)
        gpus = self.gpu_payload.get("gpus", [])
        if not gpus:
            details.update("No NVIDIA GPU data available")
            return

        lines = [f"GPU count: {self.gpu_payload.get('gpu_count', len(gpus))}", ""]
        for item in gpus:
            lines.append(
                f"GPU {item['index']} {item['name']}: util {item['utilization_percent']}% "
                f"mem {item['memory_used_mb']}/{item['memory_total_mb']} MB"
            )
        details.update("\n".join(lines))

    def action_view_pages(self) -> None:
        self.app.push_screen(OutputViewerScreen(client=self.client, job_id=self.job_id))

    def action_close(self) -> None:
        self.dismiss(None)

    @on(DataTable.RowHighlighted, "#runs-table")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        run_id = _row_key_value(event.row_key)
        if not run_id:
            return
        self.selected_run_id = run_id
        self._render_job_detail()

    @on(DataTable.RowSelected, "#runs-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        run_id = _row_key_value(event.row_key)
        if run_id:
            self.selected_run_id = run_id
        self._render_job_detail()

    @on(Button.Pressed, "#runs-view-pages")
    def on_view_pages_pressed(self) -> None:
        self.action_view_pages()

    @on(Button.Pressed, "#runs-refresh")
    async def on_refresh_pressed(self) -> None:
        await self.action_refresh()

    @on(Button.Pressed, "#runs-close")
    def on_close_pressed(self) -> None:
        self.action_close()
