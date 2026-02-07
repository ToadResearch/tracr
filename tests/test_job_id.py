from pathlib import Path

import pytest

from tracr.core.config import Settings
from tracr.core.models import LaunchJobRequest, ModelMode, OCRModelSpec
from tracr.core.pdf_tools import PDFDescriptor
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


@pytest.mark.asyncio
async def test_launch_job_uses_explicit_job_id_without_timestamp(monkeypatch, tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)

    pdf_path = tmp_path / "inputs" / "doc.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4\n%")

    monkeypatch.setattr("tracr.runtime.job_manager.expand_pdf_inputs", lambda _path: [pdf_path])
    monkeypatch.setattr(
        "tracr.runtime.job_manager.describe_pdfs",
        lambda _paths: [PDFDescriptor(path=pdf_path, page_count=1)],
    )

    async def _fake_run_job(_job_id: str, _request: LaunchJobRequest, _descriptors: list[PDFDescriptor]) -> None:
        return

    monkeypatch.setattr(manager, "_run_job", _fake_run_job)

    def _fail_build_job_id(_title: str | None, _input_path: str) -> str:
        raise AssertionError("build_job_id should not be called when job_id is provided")

    monkeypatch.setattr("tracr.runtime.job_manager.build_job_id", _fail_build_job_id)

    payload = LaunchJobRequest(
        job_id="comparison-batch",
        title=None,
        input_path=str(pdf_path),
        models=[
            OCRModelSpec(
                model="gpt-5-mini",
                mode=ModelMode.API,
                provider="openai",
                base_url="https://api.openai.com/v1",
                api_key="test-key",
            )
        ],
    )

    job = await manager.launch_job(payload)

    assert job.job_id == "comparison-batch"
    assert Path(job.metadata_path).parent.name == "comparison-batch"

    await manager.shutdown()
