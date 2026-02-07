from pathlib import Path

from tracr.core.input_discovery import discover_inputs, expand_pdf_inputs, resolve_input_path


class DummySettings:
    def __init__(self, inputs_path: Path):
        self.inputs_path = inputs_path


def test_expand_pdf_inputs_directory(tmp_path: Path) -> None:
    root = tmp_path / "inputs"
    nested = root / "nested"
    nested.mkdir(parents=True)

    (root / "a.pdf").write_bytes(b"pdf")
    (nested / "b.pdf").write_bytes(b"pdf")
    (nested / "ignore.txt").write_text("x", encoding="utf-8")

    paths = expand_pdf_inputs(root)
    names = [p.name for p in paths]

    assert names == ["a.pdf", "b.pdf"]


def test_discover_inputs_returns_pdf_and_folder_candidates(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    (inputs / "docs").mkdir(parents=True)
    (inputs / "docs" / "one.pdf").write_bytes(b"pdf")

    settings = DummySettings(inputs)
    candidates = discover_inputs(settings)

    kinds = {(item.kind, item.relative_to_inputs) for item in candidates}

    assert ("pdf", "docs/one.pdf") in kinds
    assert ("folder", "docs") in kinds


def test_resolve_input_path_prefers_inputs_folder(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "report.pdf").write_bytes(b"pdf")

    settings = DummySettings(inputs)

    resolved = resolve_input_path(settings, "report.pdf")
    assert resolved == (inputs / "report.pdf")
