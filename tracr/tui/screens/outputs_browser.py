from __future__ import annotations

import asyncio
from typing import Any

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from tracr.tui.common import _row_key_value
from tracr.tui.service_client import ServiceClient, ServiceClientError


class FocusablePreview(Static):
    can_focus = True


class OutputsBrowserScreen(ModalScreen[None]):
    CSS = """
    OutputsBrowserScreen {
      align: center middle;
    }

    #outputs-root {
      width: 98%;
      height: 98%;
      border: heavy $accent;
      background: $panel;
      padding: 0 1;
    }

    #outputs-title {
      text-style: bold;
      color: $accent;
      height: auto;
      margin-top: 1;
    }

    #outputs-path {
      color: $text-muted;
      height: auto;
      margin-bottom: 1;
    }

    #outputs-body {
      height: 1fr;
      layout: horizontal;
    }

    #outputs-table {
      width: 42%;
      margin-right: 1;
    }

    #outputs-preview {
      width: 58%;
      border: round $secondary;
      padding: 0 1;
      overflow: auto;
    }

    #outputs-help {
      color: $text-muted;
      height: auto;
      margin-top: 1;
    }

    #outputs-actions {
      height: 3;
      align-horizontal: left;
      padding-top: 1;
    }

    #outputs-actions Button {
      margin-right: 1;
      min-width: 14;
    }
    """

    BINDINGS = [
        Binding("enter", "open_selected", "Open"),
        Binding("backspace", "go_parent", "Up"),
        Binding("up", "scroll_preview_up", "Scroll Up"),
        Binding("down", "scroll_preview_down", "Scroll Down"),
        Binding("pageup", "scroll_preview_page_up", "Page Up"),
        Binding("pagedown", "scroll_preview_page_down", "Page Down"),
        Binding("r", "refresh_tree", "Refresh"),
        Binding("escape", "close", "Close"),
    ]

    def __init__(self, *, client: ServiceClient):
        super().__init__()
        self.client = client
        self.current_path = ""
        self.parent_path: str | None = None
        self.entries: list[dict[str, Any]] = []
        self.selected_relative_path: str | None = None

    def compose(self) -> ComposeResult:
        with Container(id="outputs-root"):
            yield Label("TRACR Outputs Browser", id="outputs-title")
            yield Static("", id="outputs-path")
            with Horizontal(id="outputs-body"):
                yield DataTable(id="outputs-table", cursor_type="row")
                yield FocusablePreview("Select a file or folder.", id="outputs-preview")
            yield Static(
                "Enter open | Backspace up | Up/Down/PgUp/PgDn scroll file | R refresh | Esc close",
                id="outputs-help",
            )
            with Horizontal(id="outputs-actions"):
                yield Button("Open (Enter)", id="outputs-open", variant="primary")
                yield Button("Up (Backspace)", id="outputs-up")
                yield Button("Refresh (R)", id="outputs-refresh")
                yield Button("Close (Esc)", id="outputs-close", variant="error")

    async def on_mount(self) -> None:
        table = self.query_one("#outputs-table", DataTable)
        table.add_columns("Type", "Name", "Size")
        await self._refresh_tree(preserve=False)
        self.set_focus(table)

    @staticmethod
    def _format_size(size_bytes: int | None) -> str:
        if size_bytes is None:
            return "-"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _entry_for_relative_path(self, relative_path: str | None) -> dict[str, Any] | None:
        if not relative_path:
            return None
        for entry in self.entries:
            if entry.get("relative_path") == relative_path:
                return entry
        return None

    async def _refresh_tree(self, *, preserve: bool) -> None:
        previous_selection = self.selected_relative_path if preserve else None
        try:
            payload = await asyncio.to_thread(self.client.list_outputs_tree, self.current_path)
        except ServiceClientError as exc:
            self.query_one("#outputs-path", Static).update(f"Failed to load outputs tree: {exc}")
            self.query_one("#outputs-preview", FocusablePreview).update("Unable to fetch outputs directory listing.")
            return

        self.current_path = payload.get("current_path", "")
        self.parent_path = payload.get("parent_path")
        self.entries = payload.get("entries", [])
        if preserve and previous_selection:
            self.selected_relative_path = previous_selection
        elif self.entries:
            self.selected_relative_path = self.entries[0].get("relative_path")
        else:
            self.selected_relative_path = None

        path_label = self.current_path or "/"
        self.query_one("#outputs-path", Static).update(f"Path: outputs/{path_label}")

        table = self.query_one("#outputs-table", DataTable)
        table.clear(columns=False)
        if not self.entries:
            table.add_row("·", "(empty)", "-")
            self.query_one("#outputs-preview", FocusablePreview).update("This directory is empty.")
            self.set_focus(table)
            return

        for entry in self.entries:
            icon = "DIR" if entry.get("kind") == "dir" else "FILE"
            table.add_row(
                icon,
                entry.get("name", ""),
                self._format_size(entry.get("size_bytes")),
                key=entry.get("relative_path", ""),
            )

        if self.selected_relative_path:
            try:
                row_index = table.get_row_index(self.selected_relative_path)
                table.move_cursor(row=row_index)
            except Exception:
                self.selected_relative_path = self.entries[0].get("relative_path")

        self._render_entry_preview(self._entry_for_relative_path(self.selected_relative_path))
        self.set_focus(table)

    def _render_entry_preview(self, entry: dict[str, Any] | None) -> None:
        preview = self.query_one("#outputs-preview", FocusablePreview)
        if not entry:
            preview.update("Select a file or folder.")
            return

        entry_name = entry.get("name", "")
        kind = entry.get("kind", "")
        size_text = self._format_size(entry.get("size_bytes"))
        if kind == "dir":
            preview.update(
                f"[bold cyan]{entry_name}[/bold cyan]\n"
                f"[dim]Directory[/dim]\n\n"
                "Press Enter to open."
            )
            return

        file_kind = "Metadata JSON" if entry.get("is_metadata_json") else "Markdown" if entry.get("is_markdown") else "Text"
        preview.update(
            f"[bold green]{entry_name}[/bold green]\n"
            f"[dim]{file_kind} | {size_text}[/dim]\n\n"
            "Press Enter to view file content."
        )

    async def _open_selected(self) -> None:
        entry = self._entry_for_relative_path(self.selected_relative_path)
        if not entry:
            return

        if entry.get("kind") == "dir":
            self.current_path = str(entry.get("relative_path") or "")
            await self._refresh_tree(preserve=False)
            return

        relative_path = str(entry.get("relative_path") or "")
        if not relative_path:
            return

        try:
            payload = await asyncio.to_thread(self.client.read_output_file, relative_path)
        except ServiceClientError as exc:
            self.notify(f"Open failed: {exc}", severity="error")
            return

        name = payload.get("name", relative_path)
        extension = str(payload.get("extension", "")).lower()
        content = str(payload.get("content", ""))
        size_bytes = payload.get("size_bytes")
        size_text = self._format_size(size_bytes)
        preview = self.query_one("#outputs-preview", FocusablePreview)

        header = Text(f"{name} ({size_text})", style="bold bright_white")
        if extension == ".json":
            syntax = Syntax(content or "{}", "json", theme="ansi_dark", line_numbers=False, word_wrap=True)
            preview.update(Group(header, syntax))
            self.set_focus(preview)
            return

        if extension == ".md":
            output_tokens = payload.get("output_tokens")
            output_chars = payload.get("output_characters", len(content))
            tokens_text = str(output_tokens) if output_tokens is not None else "-"
            stats = Text(f"Output tokens: {tokens_text} | Characters: {output_chars}", style="bold cyan")
            syntax = Syntax(content, "markdown", theme="ansi_dark", line_numbers=False, word_wrap=True)
            preview.update(Group(header, stats, syntax))
            self.set_focus(preview)
            return

        syntax = Syntax(content, "text", theme="ansi_dark", line_numbers=False, word_wrap=True)
        preview.update(Group(header, syntax))
        self.set_focus(preview)

    def action_close(self) -> None:
        self.dismiss(None)

    async def action_open_selected(self) -> None:
        await self._open_selected()

    async def action_go_parent(self) -> None:
        if self.parent_path is None:
            return
        self.current_path = self.parent_path
        await self._refresh_tree(preserve=False)

    async def action_refresh_tree(self) -> None:
        await self._refresh_tree(preserve=True)

    def action_scroll_preview_up(self) -> None:
        self.query_one("#outputs-preview", FocusablePreview).scroll_relative(y=-4, animate=False)

    def action_scroll_preview_down(self) -> None:
        self.query_one("#outputs-preview", FocusablePreview).scroll_relative(y=4, animate=False)

    def action_scroll_preview_page_up(self) -> None:
        self.query_one("#outputs-preview", FocusablePreview).scroll_relative(y=-16, animate=False)

    def action_scroll_preview_page_down(self) -> None:
        self.query_one("#outputs-preview", FocusablePreview).scroll_relative(y=16, animate=False)

    @on(DataTable.RowHighlighted, "#outputs-table")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        relative_path = _row_key_value(event.row_key)
        if not relative_path:
            return
        self.selected_relative_path = relative_path
        self._render_entry_preview(self._entry_for_relative_path(relative_path))

    @on(DataTable.RowSelected, "#outputs-table")
    async def on_row_selected(self, event: DataTable.RowSelected) -> None:
        relative_path = _row_key_value(event.row_key)
        if relative_path:
            self.selected_relative_path = relative_path
        await self._open_selected()

    @on(Button.Pressed, "#outputs-open")
    async def on_open_pressed(self) -> None:
        await self.action_open_selected()

    @on(Button.Pressed, "#outputs-up")
    async def on_up_pressed(self) -> None:
        await self.action_go_parent()

    @on(Button.Pressed, "#outputs-refresh")
    async def on_refresh_pressed(self) -> None:
        await self.action_refresh_tree()

    @on(Button.Pressed, "#outputs-close")
    def on_close_pressed(self) -> None:
        self.action_close()
