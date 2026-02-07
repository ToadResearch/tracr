from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tracr.core.config import REPO_ROOT, Settings
from tracr.runtime.elo_manager import EloManager
from tracr.runtime.job_manager import JobManager
from tracr.web.routes import build_web_router


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        _env_file=None,
        OCR_INPUTS_DIR=str(tmp_path / "inputs"),
        OCR_OUTPUTS_DIR=str(tmp_path / "outputs"),
        OCR_JOB_CONFIGS_DIR=str(tmp_path / "job_configs"),
        OCR_STATE_DIR=str(tmp_path / "state"),
    )
    settings.ensure_runtime_dirs()
    return settings


def _build_client(tmp_path: Path) -> tuple[TestClient, Settings]:
    settings = _build_settings(tmp_path)
    manager = JobManager(settings)
    elo_manager = EloManager(settings)
    app = FastAPI()
    app.include_router(build_web_router(settings=settings, manager=manager, elo_manager=elo_manager))
    return TestClient(app), settings


def _seed_output_tree(settings: Settings) -> None:
    job_dir = settings.outputs_path / "job-1"
    _write_json(job_dir / "job_metadata.json", {"title": "Invoice Review", "created_at": "2026-02-07T00:00:00Z"})

    _write_json(job_dir / "model-a" / "model_metadata.json", {"model": "model-a"})
    _write_json(job_dir / "model-a" / "run-1" / "run_metadata.json", {"model": "model-a"})
    _write_json(
        job_dir / "model-a" / "run-1" / "invoice" / "pdf_metadata.json",
        {
            "source_pdf": "/very/private/invoice.pdf",
            "pages": [
                {"page_number": 1, "token_usage": {"output_tokens": 12}},
                {"page_number": 2, "token_usage": {"output_tokens": 14}},
                {"page_number": 10, "token_usage": {"output_tokens": 16}},
            ],
        },
    )
    (job_dir / "model-a" / "run-1" / "invoice" / "1.md").write_text("# A output", encoding="utf-8")
    (job_dir / "model-a" / "run-1" / "invoice" / "2.md").write_text("# A output p2", encoding="utf-8")
    (job_dir / "model-a" / "run-1" / "invoice" / "10.md").write_text("# A output p10", encoding="utf-8")

    _write_json(job_dir / "model-b" / "model_metadata.json", {"model": "model-b"})
    _write_json(job_dir / "model-b" / "run-1" / "run_metadata.json", {"model": "model-b"})
    _write_json(
        job_dir / "model-b" / "run-1" / "invoice" / "pdf_metadata.json",
        {
            "source_pdf": "/very/private/invoice.pdf",
            "pages": [{"page_number": 1, "token_usage": {"output_tokens": 19}}],
        },
    )
    (job_dir / "model-b" / "run-1" / "invoice" / "1.md").write_text("# B output", encoding="utf-8")


def test_web_jobs_and_outputs_do_not_expose_source_paths(tmp_path: Path) -> None:
    client, settings = _build_client(tmp_path)
    _seed_output_tree(settings)

    jobs_resp = client.get("/api/web/jobs")
    assert jobs_resp.status_code == 200
    jobs = jobs_resp.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == "job-1"
    assert jobs[0]["title"] == "Invoice Review"
    assert jobs[0]["elo_eligible"] is True

    outputs_resp = client.get("/api/web/jobs/job-1/outputs")
    assert outputs_resp.status_code == 200
    outputs = outputs_resp.json()["outputs"]
    assert len(outputs) == 2
    assert all("source_pdf" not in row for row in outputs)
    assert all("pdf_dir" not in row for row in outputs)
    model_a_output = next(row for row in outputs if row["model_slug"] == "model-a")
    assert model_a_output["page_numbers"] == [1, 2, 10]


def test_web_viewer_and_elo_vote_flow(tmp_path: Path) -> None:
    client, settings = _build_client(tmp_path)
    _seed_output_tree(settings)

    outputs_resp = client.get("/api/web/jobs/job-1/outputs")
    assert outputs_resp.status_code == 200
    output_id = outputs_resp.json()["outputs"][0]["output_id"]

    viewer_resp = client.get(
        "/api/web/jobs/job-1/viewer/page",
        params={"output_id": output_id, "page_number": 1},
    )
    assert viewer_resp.status_code == 200
    viewer_payload = viewer_resp.json()
    assert viewer_payload["output"]["current_page"] == 1
    assert viewer_payload["output_tokens"] in {12, 19}
    assert viewer_payload["output_characters"] > 0
    assert viewer_payload["image_url"].startswith("/api/web/jobs/job-1/viewer/page-image")

    elo_jobs_resp = client.get("/api/web/elo/jobs")
    assert elo_jobs_resp.status_code == 200
    assert elo_jobs_resp.json()["jobs"][0]["job_id"] == "job-1"

    next_pair_resp = client.get("/api/web/elo/jobs/job-1/next")
    assert next_pair_resp.status_code == 200
    next_payload = next_pair_resp.json()
    assert next_payload["has_pair"] is True
    pair = next_payload["pair"]
    assert pair["page_number"] == 1
    assert pair["left"]["markdown_raw"]
    assert pair["right"]["markdown_raw"]

    vote_resp = client.post(
        "/api/web/elo/jobs/job-1/vote",
        json={
            "choice": "left_better",
            "pdf_slug": pair["pdf_slug"],
            "page_number": pair["page_number"],
            "left_model_slug": pair["left"]["model_slug"],
            "left_model_label": pair["left"]["model_label"],
            "left_run_number": pair["left"]["run_number"],
            "right_model_slug": pair["right"]["model_slug"],
            "right_model_label": pair["right"]["model_label"],
            "right_run_number": pair["right"]["run_number"],
        },
    )
    assert vote_resp.status_code == 200
    ratings = vote_resp.json()["ratings"]
    assert len(ratings) == 2

    elo_dir = settings.outputs_path / "job-1" / "elo"
    assert (elo_dir / "ratings.json").exists()
    assert (elo_dir / "votes.jsonl").exists()


def test_web_viewer_page_image_resolves_relative_source_pdf(tmp_path: Path, monkeypatch) -> None:
    client, settings = _build_client(tmp_path)
    job_dir = settings.outputs_path / "job-1"

    source_pdf_relative = f"inputs/invoice-web-route-{tmp_path.name}.pdf"
    source_pdf = REPO_ROOT / source_pdf_relative
    source_pdf.parent.mkdir(parents=True, exist_ok=True)
    source_pdf.write_bytes(b"%PDF-1.4\n")

    try:
        _write_json(job_dir / "job_metadata.json", {"title": "Invoice Review", "created_at": "2026-02-07T00:00:00Z"})
        _write_json(job_dir / "model-a" / "model_metadata.json", {"model": "model-a"})
        _write_json(job_dir / "model-a" / "run-1" / "run_metadata.json", {"model": "model-a"})
        _write_json(
            job_dir / "model-a" / "run-1" / "invoice" / "pdf_metadata.json",
            {"source_pdf": source_pdf_relative, "pages": [{"page_number": 1}]},
        )
        (job_dir / "model-a" / "run-1" / "invoice" / "1.md").write_text("# A output", encoding="utf-8")

        called_with: dict[str, object] = {}

        def _fake_render(pdf_path: Path, page_index: int, dpi: int) -> bytes:
            called_with["pdf_path"] = pdf_path
            called_with["page_index"] = page_index
            called_with["dpi"] = dpi
            return b"fake-png"

        monkeypatch.setattr("tracr.web.routes.render_pdf_page_png", _fake_render)

        outputs_resp = client.get("/api/web/jobs/job-1/outputs")
        assert outputs_resp.status_code == 200
        output_id = outputs_resp.json()["outputs"][0]["output_id"]

        image_resp = client.get(
            "/api/web/jobs/job-1/viewer/page-image",
            params={"output_id": output_id, "page_number": 1},
        )
        assert image_resp.status_code == 200
        assert image_resp.content == b"fake-png"
        assert called_with["pdf_path"] == source_pdf
        assert called_with["page_index"] == 0
    finally:
        source_pdf.unlink(missing_ok=True)


def test_web_viewer_page_image_falls_back_from_stale_absolute_source_pdf(tmp_path: Path, monkeypatch) -> None:
    client, settings = _build_client(tmp_path)
    job_dir = settings.outputs_path / "job-1"

    source_pdf = settings.inputs_path / "invoice.pdf"
    source_pdf.parent.mkdir(parents=True, exist_ok=True)
    source_pdf.write_bytes(b"%PDF-1.4\n")

    _write_json(
        job_dir / "job_metadata.json",
        {"title": "Invoice Review", "created_at": "2026-02-07T00:00:00Z", "input_path": "inputs/invoice.pdf"},
    )
    _write_json(job_dir / "model-a" / "model_metadata.json", {"model": "model-a"})
    _write_json(
        job_dir / "model-a" / "run-1" / "run_metadata.json",
        {"model": "model-a", "source_files": ["inputs/invoice.pdf"]},
    )
    _write_json(
        job_dir / "model-a" / "run-1" / "invoice" / "pdf_metadata.json",
        {"source_pdf": "/root/tracr/inputs/invoice.pdf", "pages": [{"page_number": 1}]},
    )
    (job_dir / "model-a" / "run-1" / "invoice" / "1.md").write_text("# A output", encoding="utf-8")

    called_with: dict[str, object] = {}

    def _fake_render(pdf_path: Path, page_index: int, dpi: int) -> bytes:
        called_with["pdf_path"] = pdf_path
        called_with["page_index"] = page_index
        called_with["dpi"] = dpi
        return b"fake-png"

    monkeypatch.setattr("tracr.web.routes.render_pdf_page_png", _fake_render)

    outputs_resp = client.get("/api/web/jobs/job-1/outputs")
    assert outputs_resp.status_code == 200
    output_id = outputs_resp.json()["outputs"][0]["output_id"]

    image_resp = client.get(
        "/api/web/jobs/job-1/viewer/page-image",
        params={"output_id": output_id, "page_number": 1},
    )
    assert image_resp.status_code == 200
    assert image_resp.content == b"fake-png"
    assert called_with["pdf_path"] == source_pdf
    assert called_with["page_index"] == 0
