from pathlib import Path

from tracr.core.config import Settings
from tracr.core.models import JobProgress, ModelMode, ModelRunProgress, RunStatus
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


def _make_job(job_id: str, status: RunStatus, tmp_path: Path) -> JobProgress:
    run = ModelRunProgress(
        run_id=f"{job_id}:run-1",
        model="org/model",
        mode=ModelMode.API,
        status=status,
        output_dir=str(tmp_path / "outputs" / job_id / "org-model" / "run-1"),
        total_pages=1,
        completed_pages=1 if status == RunStatus.COMPLETED else 0,
    )
    return JobProgress(
        job_id=job_id,
        title=job_id,
        input_path=str(tmp_path / "inputs" / "doc.pdf"),
        status=status,
        total_pages_all_models=1,
        completed_pages_all_models=1 if status == RunStatus.COMPLETED else 0,
        models=[run],
        metadata_path=str(tmp_path / "outputs" / job_id / "job_metadata.json"),
    )


def test_dismiss_completed_job_removes_it(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    job = _make_job("job-complete", RunStatus.COMPLETED, tmp_path)
    manager._jobs[job.job_id] = job

    dismissed, reason = manager.dismiss_job(job.job_id)

    assert dismissed is True
    assert reason is None
    assert manager.get_job(job.job_id) is None


def test_dismiss_canceled_job_removes_it(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    job = _make_job("job-canceled", RunStatus.CANCELED, tmp_path)
    manager._jobs[job.job_id] = job

    dismissed, reason = manager.dismiss_job(job.job_id)

    assert dismissed is True
    assert reason is None
    assert manager.get_job(job.job_id) is None


def test_dismiss_non_completed_job_is_rejected(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    job = _make_job("job-running", RunStatus.RUNNING, tmp_path)
    manager._jobs[job.job_id] = job

    dismissed, reason = manager.dismiss_job(job.job_id)

    assert dismissed is False
    assert reason == "only completed or canceled jobs can be dismissed"
