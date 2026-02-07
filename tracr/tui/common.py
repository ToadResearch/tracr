from __future__ import annotations

from typing import Any


DEFAULT_OCR_PROMPT = (
    "You are an OCR assistant. Extract all visible text from this PDF page and return clean markdown. "
    "Preserve headings, lists, and tables when possible. Do not add commentary."
)


def _format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    value = int(max(0, seconds))
    hours, rem = divmod(value, 3600)
    minutes, sec = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def _progress_bar(ratio: float, width: int = 18) -> str:
    ratio = max(0.0, min(1.0, ratio))
    done = int(ratio * width)
    return f"{'█' * done}{'░' * (width - done)} {ratio * 100:5.1f}%"


def _row_key_value(event_row_key: Any) -> str:
    if event_row_key is None:
        return ""
    if hasattr(event_row_key, "value"):
        value = event_row_key.value
        return "" if value is None else str(value)
    return str(event_row_key)


def _token_usage_from_stats(stats: dict[str, Any] | None) -> tuple[int, int, int]:
    token_usage = (stats or {}).get("token_usage", {})
    try:
        input_tokens = int(token_usage.get("input_tokens", 0) or 0)
    except Exception:  # noqa: BLE001
        input_tokens = 0
    try:
        output_tokens = int(token_usage.get("output_tokens", 0) or 0)
    except Exception:  # noqa: BLE001
        output_tokens = 0
    try:
        total_tokens = int(token_usage.get("total_tokens", 0) or 0)
    except Exception:  # noqa: BLE001
        total_tokens = input_tokens + output_tokens
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens
