from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from tracr.core.config import get_settings
from tracr.core.input_discovery import discover_inputs
from tracr.core.job_configs import discover_job_configs, load_job_config
from tracr.core.models import (
    CancelJobResponse,
    DismissJobResponse,
    JobOutputPageContentResponse,
    JobOutputPagesResponse,
    JobProgress,
    LaunchJobRequest,
    LaunchJobResponse,
    ListJobsResponse,
    OutputFileResponse,
    OutputTreeResponse,
    ProviderPresetResponse,
    SystemGPUStats,
)
from tracr.core.provider_presets import DEFAULT_LOCAL_MODELS, PROVIDER_PRESETS
from tracr.runtime.elo_manager import EloManager
from tracr.runtime.job_manager import JobManager
from tracr.runtime.openai_client import EndpointAuth, OpenAICompatibleOCRClient
from tracr.web.routes import build_web_router


settings = get_settings()
manager = JobManager(settings)
elo_manager = EloManager(settings)


class RawProxyRequest(BaseModel):
    base_url: str | None = None
    api_key_env: str | None = None
    api_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class RawProxyResponse(BaseModel):
    saved_to: str
    response: dict[str, Any]


class LoadJobConfigRequest(BaseModel):
    path: str


class JobWithRuntime(JobProgress):
    runtime_seconds: float = 0.0
    eta_seconds: float | None = None


def _enrich_job(job: JobProgress) -> JobWithRuntime:
    runtime = manager.job_runtime_seconds(job)
    eta = manager.estimate_eta_seconds(job)
    data = job.model_dump(mode="json")
    data["runtime_seconds"] = runtime
    data["eta_seconds"] = eta
    data["statistics"] = manager.job_statistics(job.job_id)

    run_lookup = {run.run_id: run for run in job.models}
    for run_payload in data.get("models", []):
        run_id = str(run_payload.get("run_id", ""))
        run = run_lookup.get(run_id)
        if run is None:
            continue
        run_payload["runtime_seconds"] = manager.run_runtime_seconds(run)
        run_payload["eta_seconds"] = manager.estimate_run_eta_seconds(run)
        run_payload["statistics"] = manager.run_statistics(job.job_id, run_id)

    return JobWithRuntime(**data)


def _resolve_output_path(relative_path: str | None) -> Path:
    root = settings.outputs_path.resolve()
    normalized = (relative_path or "").strip().lstrip("/")
    candidate = (root / normalized).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="relative_path must stay inside outputs directory") from exc
    return candidate


def _output_relative(path: Path) -> str:
    root = settings.outputs_path.resolve()
    if path.resolve() == root:
        return ""
    return path.resolve().relative_to(root).as_posix()


def _output_tokens_for_markdown(markdown_path: Path) -> int | None:
    if markdown_path.suffix.lower() != ".md" or not markdown_path.stem.isdigit():
        return None

    metadata_path = markdown_path.parent / "pdf_metadata.json"
    if not metadata_path.exists():
        return None

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None

    pages = payload.get("pages")
    if not isinstance(pages, list):
        return None

    page_number = int(markdown_path.stem)
    for page_entry in pages:
        if not isinstance(page_entry, dict):
            continue
        try:
            entry_page = int(page_entry.get("page_number"))
        except Exception:  # noqa: BLE001
            continue
        if entry_page != page_number:
            continue
        token_usage = page_entry.get("token_usage")
        if not isinstance(token_usage, dict):
            return None
        try:
            return int(token_usage.get("output_tokens"))
        except Exception:  # noqa: BLE001
            return None

    return None


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        await manager.shutdown()


app = FastAPI(title="TRACR", version="0.1.0", lifespan=lifespan)
app.include_router(build_web_router(settings=settings, manager=manager, elo_manager=elo_manager))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now(UTC).isoformat()}


@app.get("/api/presets", response_model=list[ProviderPresetResponse])
def list_presets() -> list[ProviderPresetResponse]:
    return [ProviderPresetResponse(**preset.__dict__) for preset in PROVIDER_PRESETS]


@app.get("/api/local-default-models", response_model=list[str])
def list_local_default_models() -> list[str]:
    return list(DEFAULT_LOCAL_MODELS)


@app.get("/api/inputs")
def list_inputs() -> dict[str, Any]:
    candidates = discover_inputs(settings)
    return {
        "inputs_root": str(settings.inputs_path),
        "candidates": [candidate.model_dump() for candidate in candidates],
    }


@app.get("/api/job-configs")
def list_job_configs() -> dict[str, Any]:
    candidates = discover_job_configs(settings)
    return {
        "job_configs_root": str(settings.job_configs_path),
        "candidates": candidates,
    }


@app.post("/api/job-configs/load")
def load_job_config_file(payload: LoadJobConfigRequest) -> dict[str, Any]:
    try:
        request = load_job_config(settings, payload.path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load job config: {exc}") from exc
    return request.model_dump(exclude_none=True)


@app.post("/api/jobs", response_model=LaunchJobResponse)
async def launch_job(payload: LaunchJobRequest) -> LaunchJobResponse:
    try:
        job = await manager.launch_job(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return LaunchJobResponse(job=_enrich_job(job))


@app.get("/api/jobs", response_model=ListJobsResponse)
def list_jobs() -> ListJobsResponse:
    jobs = [_enrich_job(job) for job in manager.list_jobs()]
    jobs.sort(key=lambda item: item.created_at, reverse=True)
    return ListJobsResponse(jobs=jobs)


@app.get("/api/jobs/{job_id}", response_model=JobWithRuntime)
def get_job(job_id: str) -> JobWithRuntime:
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return _enrich_job(job)


@app.post("/api/jobs/{job_id}/cancel", response_model=CancelJobResponse)
def cancel_job(job_id: str) -> CancelJobResponse:
    canceled = manager.cancel_job(job_id)
    if not canceled:
        raise HTTPException(status_code=404, detail="job not found")
    return CancelJobResponse(job_id=job_id, canceled=True)


@app.post("/api/jobs/{job_id}/dismiss", response_model=DismissJobResponse)
def dismiss_job(job_id: str) -> DismissJobResponse:
    dismissed, reason = manager.dismiss_job(job_id)
    if not dismissed:
        if reason == "job not found":
            raise HTTPException(status_code=404, detail=reason)
        raise HTTPException(status_code=400, detail=reason or "unable to dismiss job")
    return DismissJobResponse(job_id=job_id, dismissed=True)


@app.get("/api/jobs/{job_id}/output-pages", response_model=JobOutputPagesResponse)
def list_job_output_pages(job_id: str) -> JobOutputPagesResponse:
    try:
        pages = manager.list_output_pages(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JobOutputPagesResponse(job_id=job_id, pages=pages)


@app.get("/api/jobs/{job_id}/output-pages/{page_index}", response_model=JobOutputPageContentResponse)
def get_job_output_page(job_id: str, page_index: int) -> JobOutputPageContentResponse:
    try:
        payload = manager.get_output_page(job_id, page_index)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed reading page output: {exc}") from exc
    return JobOutputPageContentResponse(job_id=job_id, page=payload["page"], markdown=payload["markdown"])


@app.get("/api/outputs/tree", response_model=OutputTreeResponse)
def list_outputs_tree(relative_path: str = "") -> OutputTreeResponse:
    target = _resolve_output_path(relative_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"path not found: {relative_path}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="relative_path must point to a directory")

    entries: list[dict[str, Any]] = []
    children = sorted(target.iterdir(), key=lambda item: (0 if item.is_dir() else 1, item.name.lower()))
    for child in children:
        entries.append(
            {
                "name": child.name,
                "relative_path": _output_relative(child),
                "kind": "dir" if child.is_dir() else "file",
                "size_bytes": None if child.is_dir() else child.stat().st_size,
                "is_metadata_json": child.is_file() and child.suffix.lower() == ".json",
                "is_markdown": child.is_file() and child.suffix.lower() == ".md",
            }
        )

    current_relative = _output_relative(target)
    root = settings.outputs_path.resolve()
    parent_path = _output_relative(target.parent) if target.resolve() != root else None

    return OutputTreeResponse(
        outputs_root=str(settings.outputs_path),
        current_path=current_relative,
        parent_path=parent_path,
        entries=entries,
    )


@app.get("/api/outputs/file", response_model=OutputFileResponse)
def read_output_file(relative_path: str) -> OutputFileResponse:
    if not relative_path.strip():
        raise HTTPException(status_code=400, detail="relative_path is required")

    target = _resolve_output_path(relative_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"path not found: {relative_path}")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="relative_path must point to a file")

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"failed to read file: {exc}") from exc

    output_characters = len(content) if target.suffix.lower() == ".md" else None
    output_tokens = _output_tokens_for_markdown(target)

    return OutputFileResponse(
        relative_path=_output_relative(target),
        name=target.name,
        extension=target.suffix.lower(),
        size_bytes=target.stat().st_size,
        content=content,
        output_tokens=output_tokens,
        output_characters=output_characters,
    )


@app.get("/api/system/gpus", response_model=SystemGPUStats)
def gpu_stats() -> SystemGPUStats:
    payload = manager.gpu_stats()
    return SystemGPUStats(**payload)


@app.get("/api/providers/{provider_key}/key-status")
def provider_key_status(provider_key: str, api_key_env: str | None = None) -> dict[str, Any]:
    return manager.resolve_provider_key_status(provider_key, api_key_env)


@app.post("/api/proxy/chat/completions", response_model=RawProxyResponse)
def raw_proxy_chat(payload: RawProxyRequest) -> RawProxyResponse:
    base_url = payload.base_url or settings.default_upstream_base_url
    if not base_url:
        raise HTTPException(status_code=400, detail="Missing base_url and OCR_DEFAULT_UPSTREAM_BASE_URL")

    try:
        api_key = OpenAICompatibleOCRClient.resolve_api_key(
            payload.api_key or settings.default_upstream_api_key,
            payload.api_key_env,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    client = OpenAICompatibleOCRClient(EndpointAuth(base_url=base_url, api_key=api_key))
    try:
        response = client.raw_chat_completion(payload.payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        client.close()

    proxy_dir = settings.outputs_path / "proxy_logs"
    proxy_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    output_path = proxy_dir / f"{stamp}.json"
    output_path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "base_url": base_url,
                "request": payload.payload,
                "response": response,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return RawProxyResponse(saved_to=str(output_path), response=response)
