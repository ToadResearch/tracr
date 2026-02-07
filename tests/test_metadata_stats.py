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

    assert stats["pages_attempted"] == 2
    assert stats["pages_succeeded"] == 2
    assert stats["pages_failed"] == 0
    assert stats["token_usage"]["input_tokens"] == 100
    assert stats["token_usage"]["output_tokens"] == 70
    assert stats["token_usage"]["total_tokens"] == 170
