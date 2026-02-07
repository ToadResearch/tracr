import json
from pathlib import Path

from tracr.core.config import Settings
from tracr.runtime.job_manager import JobManager


def _build_manager(tmp_path: Path) -> JobManager:
    settings = Settings(
        _env_file=None,
        OCR_INPUTS_DIR=str(tmp_path / "inputs"),
        OCR_OUTPUTS_DIR=str(tmp_path / "outputs"),
        OCR_STATE_DIR=str(tmp_path / "state"),
    )
    settings.ensure_runtime_dirs()
    return JobManager(settings)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_list_output_pages_sorted_and_indexed(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    job_dir = manager.layout.job_dir("job-1")

    run_dir = job_dir / "model-b" / "run-2"
    _write_json(run_dir / "run_metadata.json", {"model": "org/model-b", "mode": "api"})
    _write_json(
        run_dir / "scan" / "pdf_metadata.json",
        {
            "source_pdf": "/tmp/scan.pdf",
            "pages": [
                {"page_number": 2, "token_usage": {"output_tokens": 5}},
                {"page_number": 10, "token_usage": {"output_tokens": 11}},
            ],
        },
    )
    (run_dir / "scan" / "10.md").write_text("ten", encoding="utf-8")
    (run_dir / "scan" / "2.md").write_text("two", encoding="utf-8")

    run_dir = job_dir / "model-a" / "run-1"
    _write_json(run_dir / "run_metadata.json", {"model": "org/model-a", "mode": "local"})
    _write_json(
        run_dir / "doc" / "pdf_metadata.json",
        {"source_pdf": "/tmp/doc.pdf", "pages": [{"page_number": 1, "token_usage": {"output_tokens": 3}}]},
    )
    (run_dir / "doc" / "1.md").write_text("one", encoding="utf-8")

    pages = manager.list_output_pages("job-1")

    assert [page["index"] for page in pages] == [0, 1, 2]
    assert [(page["model_slug"], page["run_number"], page["pdf_slug"], page["page_number"]) for page in pages] == [
        ("model-a", 1, "doc", 1),
        ("model-b", 2, "scan", 2),
        ("model-b", 2, "scan", 10),
    ]
    assert [page["output_tokens"] for page in pages] == [3, 5, 11]


def test_get_output_page_reads_markdown(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    run_dir = manager.layout.job_dir("job-2") / "model-x" / "run-1"

    _write_json(run_dir / "run_metadata.json", {"model": "org/model-x", "mode": "api"})
    _write_json(
        run_dir / "paper" / "pdf_metadata.json",
        {"source_pdf": "/tmp/paper.pdf", "pages": [{"page_number": 1, "token_usage": {"output_tokens": 17}}]},
    )
    (run_dir / "paper" / "1.md").write_text("# page one", encoding="utf-8")

    payload = manager.get_output_page("job-2", 0)

    assert payload["page"]["model"] == "org/model-x"
    assert payload["page"]["page_number"] == 1
    assert payload["page"]["output_tokens"] == 17
    assert payload["page"]["output_characters"] == len("# page one")
    assert payload["markdown"] == "# page one"
