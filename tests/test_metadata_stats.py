import json
from datetime import UTC, datetime
from pathlib import Path

from tracr.core.config import Settings
from tracr.core.models import JobProgress, ModelMode, ModelRunProgress
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


def test_token_usage_extraction_handles_openai_shape() -> None:
    usage = {"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165}
    totals = JobManager._token_usage_from_provider_usage(usage)
    assert totals == {"input_tokens": 120, "output_tokens": 45, "total_tokens": 165}


def test_pdf_metadata_persists_page_and_global_stats(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)

    manager.layout.ensure_job("job-m", {"job_id": "job-m"})
    run_paths = manager.layout.prepare_run("job-m", "org/model-a", {"model": "org/model-a"})
    pdf_paths = manager.layout.prepare_pdf(run_paths.run_dir, Path("/tmp/sample.pdf"), page_count=3)

    started_at = datetime.now(UTC)
    pages = [
        {
            "page_number": 1,
            "status": "completed",
            "processing_time_seconds": 1.5,
            "ocr_request_time_seconds": 1.2,
            "token_usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        },
        {
            "page_number": 2,
            "status": "failed",
            "processing_time_seconds": 2.0,
            "ocr_request_time_seconds": 0.0,
            "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "error": "upstream timeout",
        },
    ]
    manager._persist_pdf_metadata(
        pdf_metadata_path=pdf_paths.pdf_metadata_path,
        source_pdf=Path("/tmp/sample.pdf"),
        pdf_slug=pdf_paths.pdf_slug,
        page_count=3,
        pages=pages,
        started_at=started_at,
        ended_at=datetime.now(UTC),
    )

    payload = json.loads(pdf_paths.pdf_metadata_path.read_text(encoding="utf-8"))
    stats = payload["statistics"]

    assert stats["page_count"] == 3
    assert stats["processed_pages"] == 2
    assert stats["pages_succeeded"] == 1
    assert stats["pages_failed"] == 1
    assert stats["token_usage"]["input_tokens"] == 10
    assert stats["token_usage"]["output_tokens"] == 20
    assert stats["token_usage"]["total_tokens"] == 30
    assert len(payload["pages"]) == 2


def test_job_metadata_includes_rollup_statistics(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    manager._project_root = tmp_path.resolve()

    run = ModelRunProgress(
        run_id="model-a:1",
        model="org/model-a",
        mode=ModelMode.API,
        output_dir=str(tmp_path / "outputs" / "job-s" / "model-a" / "1"),
        total_pages=2,
        completed_pages=2,
    )
    job = JobProgress(
        job_id="job-s",
        title="job-s",
        input_path=str(tmp_path / "inputs" / "doc.pdf"),
        total_pages_all_models=2,
        completed_pages_all_models=2,
        models=[run],
        metadata_path=str(tmp_path / "outputs" / "job-s" / "job_metadata.json"),
    )

    manager._jobs[job.job_id] = job
    manager._run_metrics[manager._run_metrics_key(job.job_id, run.run_id)] = {
        "pages_attempted": 2,
        "pages_succeeded": 2,
        "pages_failed": 0,
        "processing_time_seconds": 3.5,
        "ocr_request_time_seconds": 2.8,
        "token_usage": {"input_tokens": 100, "output_tokens": 70, "total_tokens": 170},
    }

    manager._persist_job_metadata(job.job_id)

    payload = json.loads(Path(job.metadata_path).read_text(encoding="utf-8"))
    stats = payload["statistics"]

    assert payload["input_path"] == "inputs/doc.pdf"
    assert payload["models"][0]["output_dir"] == "outputs/job-s/model-a/1"
    assert stats["pages_attempted"] == 2
    assert stats["pages_succeeded"] == 2
    assert stats["pages_failed"] == 0
    assert stats["token_usage"]["input_tokens"] == 100
    assert stats["token_usage"]["output_tokens"] == 70
    assert stats["token_usage"]["total_tokens"] == 170


def test_job_metadata_merges_existing_runs_for_reused_job_id(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    manager._project_root = tmp_path.resolve()

    metadata_path = tmp_path / "outputs" / "job-s" / "job_metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    existing_payload = {
        "job_id": "job-s",
        "title": "job-s",
        "input_path": "inputs/doc.pdf",
        "status": "completed",
        "created_at": "2026-02-07T00:00:00+00:00",
        "started_at": "2026-02-07T00:00:05+00:00",
        "ended_at": "2026-02-07T00:10:00+00:00",
        "prompt": "ocr",
        "total_pages_all_models": 2,
        "completed_pages_all_models": 2,
        "progress_ratio": 1.0,
        "models": [
            {
                "run_id": "model-a:1",
                "model": "org/model-a",
                "mode": "api",
                "status": "completed",
                "started_at": "2026-02-07T00:00:05+00:00",
                "ended_at": "2026-02-07T00:10:00+00:00",
                "total_pages": 2,
                "completed_pages": 2,
                "output_dir": "outputs/job-s/model-a/run-1",
                "source_files": ["inputs/doc.pdf"],
                "runtime_seconds": 10.0,
                "statistics": {
                    "pages_attempted": 2,
                    "pages_succeeded": 2,
                    "pages_failed": 0,
                    "processing_time_seconds": 3.0,
                    "ocr_request_time_seconds": 2.0,
                    "token_usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                },
            }
        ],
        "statistics": {
            "pages_attempted": 2,
            "pages_succeeded": 2,
            "pages_failed": 0,
            "processing_time_seconds": 3.0,
            "ocr_request_time_seconds": 2.0,
            "runtime_seconds": 10.0,
            "token_usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        },
    }
    metadata_path.write_text(json.dumps(existing_payload), encoding="utf-8")

    run = ModelRunProgress(
        run_id="model-b:1",
        model="org/model-b",
        mode=ModelMode.API,
        output_dir=str(tmp_path / "outputs" / "job-s" / "model-b" / "run-1"),
        total_pages=3,
        completed_pages=1,
    )
    job = JobProgress(
        job_id="job-s",
        title="job-s",
        input_path=str(tmp_path / "inputs" / "doc.pdf"),
        total_pages_all_models=3,
        completed_pages_all_models=1,
        models=[run],
        metadata_path=str(metadata_path),
    )

    manager._jobs[job.job_id] = job
    manager._run_metrics[manager._run_metrics_key(job.job_id, run.run_id)] = {
        "pages_attempted": 1,
        "pages_succeeded": 1,
        "pages_failed": 0,
        "processing_time_seconds": 1.5,
        "ocr_request_time_seconds": 1.0,
        "token_usage": {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12},
    }

    manager._persist_job_metadata(job.job_id)

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    run_ids = {entry.get("run_id") for entry in payload["models"]}

    assert run_ids == {"model-a:1", "model-b:1"}
    assert payload["created_at"] == "2026-02-07T00:00:00+00:00"
    assert payload["total_pages_all_models"] == 5
    assert payload["completed_pages_all_models"] == 3
    assert payload["status"] == "queued"

    stats = payload["statistics"]
    assert stats["pages_attempted"] == 3
    assert stats["pages_succeeded"] == 3
    assert stats["pages_failed"] == 0
    assert stats["token_usage"]["input_tokens"] == 15
    assert stats["token_usage"]["output_tokens"] == 27
    assert stats["token_usage"]["total_tokens"] == 42
