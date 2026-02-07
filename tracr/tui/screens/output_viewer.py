from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from tracr.tui.service_client import ServiceClient, ServiceClientError


class OutputViewerScreen(ModalScreen[None]):
    CSS = """
    OutputViewerScreen {
      align: center middle;
    }

    #viewer-root {
      width: 98%;
      height: 98%;
      border: heavy $accent;
      background: $panel;
      padding: 0 1;
    }

    #viewer-title {
      text-style: bold;
      color: $accent;
      height: auto;
      margin-top: 1;
    }

    #viewer-meta {
      color: $text-muted;
      height: auto;
      margin-bottom: 1;
    }

    #viewer-content {
      height: 1fr;
      border: round $secondary;
      padding: 0 1;
      overflow: auto;
    }

    #viewer-help {
      color: $text-muted;
      height: auto;
      margin-top: 1;
    }

    #viewer-actions {
      height: 3;
      align-horizontal: left;
      padding-top: 1;
    }

    #viewer-actions Button {
      margin-right: 1;
      min-width: 14;
    }
    """

    BINDINGS = [
        Binding("left", "prev_page", "Prev"),
        Binding("right", "next_page", "Next"),
        Binding("up", "scroll_up", "Up"),
        Binding("down", "scroll_down", "Down"),
        Binding("r", "refresh_pages", "Refresh"),
        Binding("escape", "close", "Close"),
    ]

    def __init__(self, *, client: ServiceClient, job_id: str):
        super().__init__()
        self.client = client
        self.job_id = job_id
        self.pages: list[dict[str, Any]] = []
        self.current_index = 0

    def compose(self) -> ComposeResult:
        with Container(id="viewer-root"):
            yield Label(f"TRACR Output Viewer - {self.job_id}", id="viewer-title")
            yield Static("", id="viewer-meta")
            yield Static("Loading...", id="viewer-content")
            yield Static("Left/Right switch page | Up/Down scroll | R refresh | Esc close", id="viewer-help")
            with Horizontal(id="viewer-actions"):
                yield Button("Prev (Left)", id="viewer-prev")
                yield Button("Next (Right)", id="viewer-next")
                yield Button("Refresh (R)", id="viewer-refresh")
                yield Button("Close (Esc)", id="viewer-close", variant="error")

    async def on_mount(self) -> None:
        await self._refresh_pages(preserve=False)

    @staticmethod
    def _page_identity(page: dict[str, Any]) -> tuple[str, int, str, int]:
        return (
            str(page.get("model_slug", "")),
            int(page.get("run_number", 0)),
            str(page.get("pdf_slug", "")),
            int(page.get("page_number", 0)),
        )

    async def _refresh_pages(self, *, preserve: bool) -> None:
        previous_identity: tuple[str, int, str, int] | None = None
        if self.pages and 0 <= self.current_index < len(self.pages):
            previous_identity = self._page_identity(self.pages[self.current_index])

        try:
            payload = await asyncio.to_thread(self.client.list_job_output_pages, self.job_id)
        except ServiceClientError as exc:
            self.query_one("#viewer-meta", Static).update(f"Failed to load pages: {exc}")
            self.query_one("#viewer-content", Static).update("Unable to fetch output pages from API.")
            self._update_nav_buttons()
            return

        self.pages = payload.get("pages", [])

        if not self.pages:
            self.current_index = 0
            self.query_one("#viewer-meta", Static).update(
                f"Job {self.job_id}: no completed pages yet. Press R to refresh."
            )
            self.query_one("#viewer-content", Static).update(
                "No page markdown files found yet for this job."
            )
            self._update_nav_buttons()
            return

        if preserve and previous_identity:
            for idx, page in enumerate(self.pages):
                if self._page_identity(page) == previous_identity:
                    self.current_index = idx
                    break
            else:
                self.current_index = min(self.current_index, len(self.pages) - 1)
        else:
            self.current_index = min(self.current_index, len(self.pages) - 1)

        await self._load_current_page(reset_scroll=True)

    async def _load_current_page(self, *, reset_scroll: bool) -> None:
        if not self.pages:
            return

        current = self.pages[self.current_index]
        page_index = int(current.get("index", self.current_index))

        try:
            payload = await asyncio.to_thread(self.client.get_job_output_page, self.job_id, page_index)
        except ServiceClientError as exc:
            self.query_one("#viewer-meta", Static).update(f"Failed to load page: {exc}")
            self.query_one("#viewer-content", Static).update("Unable to fetch selected page markdown.")
            self._update_nav_buttons()
            return

        page = payload.get("page", current)
        markdown = payload.get("markdown", "")
        source_pdf = page.get("source_pdf")
        source_tail = f" | pdf: {Path(source_pdf).name}" if source_pdf else ""
        output_tokens = page.get("output_tokens")
        output_chars = page.get("output_characters")
        if output_chars is None:
            output_chars = len(markdown or "")
        tokens_text = str(output_tokens) if output_tokens is not None else "-"

        self.query_one("#viewer-meta", Static).update(
            f"Page {self.current_index + 1}/{len(self.pages)}"
            f" | model: {page.get('model')} (run {page.get('run_number')})"
            f" | {page.get('pdf_slug')}#{page.get('page_number')}"
            f" | out_tokens: {tokens_text} | chars: {output_chars}"
            f"{source_tail}"
        )
        content = self.query_one("#viewer-content", Static)
        content.update(markdown or "<empty markdown output>")
        if reset_scroll:
            content.scroll_home(animate=False)

        self._update_nav_buttons()

    def _update_nav_buttons(self) -> None:
        prev_btn = self.query_one("#viewer-prev", Button)
        next_btn = self.query_one("#viewer-next", Button)
        refresh_btn = self.query_one("#viewer-refresh", Button)

        has_pages = bool(self.pages)
        prev_btn.disabled = (not has_pages) or self.current_index <= 0
        next_btn.disabled = (not has_pages) or self.current_index >= len(self.pages) - 1
        refresh_btn.disabled = False

    async def action_prev_page(self) -> None:
        if not self.pages or self.current_index <= 0:
            return
        self.current_index -= 1
        await self._load_current_page(reset_scroll=True)

    async def action_next_page(self) -> None:
        if not self.pages or self.current_index >= len(self.pages) - 1:
            return
        self.current_index += 1
        await self._load_current_page(reset_scroll=True)

    def action_scroll_up(self) -> None:
        self.query_one("#viewer-content", Static).scroll_relative(y=-4, animate=False)

    def action_scroll_down(self) -> None:
        self.query_one("#viewer-content", Static).scroll_relative(y=4, animate=False)

    async def action_refresh_pages(self) -> None:
        await self._refresh_pages(preserve=True)

    def action_close(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#viewer-prev")
    async def on_prev_pressed(self) -> None:
        await self.action_prev_page()

    @on(Button.Pressed, "#viewer-next")
    async def on_next_pressed(self) -> None:
        await self.action_next_page()

    @on(Button.Pressed, "#viewer-refresh")
    async def on_refresh_pressed(self) -> None:
        await self.action_refresh_pages()

    @on(Button.Pressed, "#viewer-close")
    def on_close_pressed(self) -> None:
        self.action_close()
