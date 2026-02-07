from __future__ import annotations

from pathlib import Path

from tracr.core.config import Settings
from tracr.core.models import InputCandidate


PDF_SUFFIXES = {".pdf"}


def is_pdf(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in PDF_SUFFIXES


def resolve_input_path(settings: Settings, candidate: str) -> Path:
    raw = Path(candidate).expanduser()
    if raw.is_absolute():
        return raw

    direct = (Path.cwd() / raw).resolve()
    if direct.exists():
        return direct

    from_inputs = (settings.inputs_path / raw).resolve()
    return from_inputs


def expand_pdf_inputs(source: Path) -> list[Path]:
    if source.is_file() and is_pdf(source):
        return [source]
    if source.is_dir():
        return sorted(path for path in source.rglob("*.pdf") if path.is_file())
    return []


def discover_inputs(settings: Settings, max_items: int = 500) -> list[InputCandidate]:
    inputs_root = settings.inputs_path
    inputs_root.mkdir(parents=True, exist_ok=True)

    candidates: list[InputCandidate] = []
    seen_dirs: set[Path] = set()

    for path in sorted(inputs_root.rglob("*")):
        if len(candidates) >= max_items:
            break

        if is_pdf(path):
            candidates.append(
                InputCandidate(
                    path=str(path),
                    kind="pdf",
                    relative_to_inputs=str(path.relative_to(inputs_root)),
                )
            )

            parent = path.parent
            if parent != inputs_root and parent not in seen_dirs:
                seen_dirs.add(parent)
                candidates.append(
                    InputCandidate(
                        path=str(parent),
                        kind="folder",
                        relative_to_inputs=str(parent.relative_to(inputs_root)),
                    )
                )

    return candidates
