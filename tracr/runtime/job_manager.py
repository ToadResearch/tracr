from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tracr.core.config import REPO_ROOT, Settings
from tracr.core.input_discovery import expand_pdf_inputs, resolve_input_path
from tracr.core.models import (
    JobProgress,
    LaunchJobRequest,
    ModelMode,
    ModelRunProgress,
    RunStatus,
)
from tracr.core.output_layout import OutputLayout, RunPaths, build_job_id, write_json
from tracr.core.pdf_tools import PDFDescriptor, describe_pdfs, iter_rendered_pages
from tracr.core.provider_presets import PRESET_BY_KEY
from tracr.runtime.openai_client import OCRPageResult, EndpointAuth, OpenAICompatibleOCRClient
from tracr.runtime.vllm_manager import ServerHandle, VLLMServerManager


@dataclass
class _RunContext:
    run_paths: RunPaths
    run: ModelRunProgress
    spec_index: int


@dataclass
class _PageOCROutcome:
    page_number: int
    markdown_text: str
    usage_payload: dict[str, Any] | None
    finish_reason: str | None
    provider_model: str | None
    attempts: int
    request_seconds: float | None
    error_text: str | None
    page_started_at: datetime
    page_ended_at: datetime
    processing_seconds: float


class JobManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.layout = OutputLayout(settings)
        self.vllm_manager = VLLMServerManager(settings)
        self._project_root = REPO_ROOT.resolve()

        self._state_lock = threading.RLock()
        self._jobs: dict[str, JobProgress] = {}
        self._job_contexts: dict[str, list[_RunContext]] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._run_metrics: dict[str, dict[str, Any]] = {}

    def _to_project_relative_path(self, value: str | Path | None) -> str | None:
        if value is None:
            return None

        raw = str(value).strip()
        if not raw:
            return raw

        path = Path(raw).expanduser()
        if not path.is_absolute():
            return path.as_posix()

        try:
            return path.resolve().relative_to(self._project_root).as_posix()
        except Exception:  # noqa: BLE001
            return str(path)

    def _serialize_run_for_job_metadata(self, run: ModelRunProgress) -> dict[str, Any]:
        payload = run.model_dump(mode="json")
        payload["output_dir"] = self._to_project_relative_path(payload.get("output_dir"))
        payload["current_pdf"] = self._to_project_relative_path(payload.get("current_pdf"))

        source_files = payload.get("source_files")
        if isinstance(source_files, list):
            payload["source_files"] = [
                rel
                for rel in (self._to_project_relative_path(item) for item in source_files)
                if rel
            ]
        return payload

    @staticmethod
    def _run_metrics_key(job_id: str, run_id: str) -> str:
        return f"{job_id}::{run_id}"

    @staticmethod
    def _new_token_usage() -> dict[str, int]:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    @classmethod
    def _new_metrics(cls) -> dict[str, Any]:
        return {
            "pages_attempted": 0,
            "pages_succeeded": 0,
            "pages_failed": 0,
            "processing_time_seconds": 0.0,
            "ocr_request_time_seconds": 0.0,
            "token_usage": cls._new_token_usage(),
        }

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except Exception:  # noqa: BLE001
            return 0

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        try:
            return int(value)
        except Exception:  # noqa: BLE001
            return None

    @classmethod
    def _token_usage_from_provider_usage(cls, usage: dict[str, Any] | None) -> dict[str, int]:
        if not usage:
            return cls._new_token_usage()

        input_tokens = cls._safe_int(usage.get("prompt_tokens", usage.get("input_tokens", 0)))
        output_tokens = cls._safe_int(usage.get("completion_tokens", usage.get("output_tokens", 0)))
        total_tokens = cls._safe_int(usage.get("total_tokens", 0))
        if total_tokens <= 0:
            total_tokens = input_tokens + output_tokens

        return {
            "input_tokens": max(0, input_tokens),
            "output_tokens": max(0, output_tokens),
            "total_tokens": max(0, total_tokens),
        }

    @classmethod
    def _merge_token_usage(cls, target: dict[str, Any], source: dict[str, Any]) -> None:
        target["input_tokens"] = cls._safe_int(target.get("input_tokens")) + cls._safe_int(source.get("input_tokens"))
        target["output_tokens"] = cls._safe_int(target.get("output_tokens")) + cls._safe_int(source.get("output_tokens"))
        target["total_tokens"] = cls._safe_int(target.get("total_tokens")) + cls._safe_int(source.get("total_tokens"))

    @classmethod
    def _finalize_metrics(cls, metrics: dict[str, Any], runtime_seconds: float | None = None) -> dict[str, Any]:
        pages_attempted = max(0, cls._safe_int(metrics.get("pages_attempted")))
        processing_time = max(0.0, float(metrics.get("processing_time_seconds", 0.0)))
        request_time = max(0.0, float(metrics.get("ocr_request_time_seconds", 0.0)))
        token_usage = cls._new_token_usage()
        cls._merge_token_usage(token_usage, metrics.get("token_usage", {}))

        finalized = {
            "pages_attempted": pages_attempted,
            "pages_succeeded": max(0, cls._safe_int(metrics.get("pages_succeeded"))),
            "pages_failed": max(0, cls._safe_int(metrics.get("pages_failed"))),
            "processing_time_seconds": processing_time,
            "ocr_request_time_seconds": request_time,
            "average_processing_time_seconds": (processing_time / pages_attempted) if pages_attempted > 0 else 0.0,
            "average_ocr_request_time_seconds": (request_time / pages_attempted) if pages_attempted > 0 else 0.0,
            "token_usage": token_usage,
        }
        if runtime_seconds is not None:
            finalized["runtime_seconds"] = max(0.0, runtime_seconds)
        return finalized

    def _run_statistics(self, job_id: str, run_id: str) -> dict[str, Any]:
        key = self._run_metrics_key(job_id, run_id)
        with self._state_lock:
            metrics = self._run_metrics.get(key, self._new_metrics())
            # deep-ish copy for serialization safety
            copied = {
                "pages_attempted": metrics.get("pages_attempted", 0),
                "pages_succeeded": metrics.get("pages_succeeded", 0),
                "pages_failed": metrics.get("pages_failed", 0),
                "processing_time_seconds": metrics.get("processing_time_seconds", 0.0),
                "ocr_request_time_seconds": metrics.get("ocr_request_time_seconds", 0.0),
                "token_usage": dict(metrics.get("token_usage", self._new_token_usage())),
            }
        return self._finalize_metrics(copied)

    def _record_run_page_metrics(
        self,
        *,
        job_id: str,
        run_id: str,
        succeeded: bool,
        processing_time_seconds: float,
        ocr_request_time_seconds: float | None,
        token_usage: dict[str, Any],
    ) -> None:
        key = self._run_metrics_key(job_id, run_id)
        with self._state_lock:
            metrics = self._run_metrics.setdefault(key, self._new_metrics())
            metrics["pages_attempted"] = self._safe_int(metrics.get("pages_attempted")) + 1
            if succeeded:
                metrics["pages_succeeded"] = self._safe_int(metrics.get("pages_succeeded")) + 1
            else:
                metrics["pages_failed"] = self._safe_int(metrics.get("pages_failed")) + 1
            metrics["processing_time_seconds"] = float(metrics.get("processing_time_seconds", 0.0)) + max(
                0.0, float(processing_time_seconds)
            )
            metrics["ocr_request_time_seconds"] = float(metrics.get("ocr_request_time_seconds", 0.0)) + max(
                0.0, float(ocr_request_time_seconds or 0.0)
            )
            token_totals = metrics.setdefault("token_usage", self._new_token_usage())
            self._merge_token_usage(token_totals, token_usage)

    def _job_statistics(self, job: JobProgress) -> dict[str, Any]:
        aggregate = self._new_metrics()
        for run in job.models:
            run_stats = self._run_statistics(job.job_id, run.run_id)
            aggregate["pages_attempted"] += self._safe_int(run_stats.get("pages_attempted"))
            aggregate["pages_succeeded"] += self._safe_int(run_stats.get("pages_succeeded"))
            aggregate["pages_failed"] += self._safe_int(run_stats.get("pages_failed"))
            aggregate["processing_time_seconds"] += float(run_stats.get("processing_time_seconds", 0.0))
            aggregate["ocr_request_time_seconds"] += float(run_stats.get("ocr_request_time_seconds", 0.0))
            self._merge_token_usage(aggregate["token_usage"], run_stats.get("token_usage", {}))

        return self._finalize_metrics(aggregate, runtime_seconds=self.job_runtime_seconds(job))

    @classmethod
    def _pdf_statistics(cls, page_count: int, pages: list[dict[str, Any]]) -> dict[str, Any]:
        aggregate = cls._new_metrics()
        for page in pages:
            status = str(page.get("status", "")).lower()
            aggregate["pages_attempted"] += 1
            if status == "completed":
                aggregate["pages_succeeded"] += 1
            else:
                aggregate["pages_failed"] += 1
            aggregate["processing_time_seconds"] += float(page.get("processing_time_seconds", 0.0))
            aggregate["ocr_request_time_seconds"] += float(page.get("ocr_request_time_seconds") or 0.0)
            cls._merge_token_usage(aggregate["token_usage"], page.get("token_usage", {}))

        finalized = cls._finalize_metrics(aggregate)
        finalized["page_count"] = max(0, page_count)
        finalized["processed_pages"] = finalized["pages_attempted"]
        return finalized

    @classmethod
    def _output_tokens_from_pdf_metadata(cls, pdf_metadata: dict[str, Any], page_number: int) -> int | None:
        pages = pdf_metadata.get("pages")
        if not isinstance(pages, list):
            return None

        for page_entry in pages:
            if not isinstance(page_entry, dict):
                continue
            entry_page_number = cls._optional_int(page_entry.get("page_number"))
            if entry_page_number != page_number:
                continue
            token_usage = page_entry.get("token_usage")
            if not isinstance(token_usage, dict):
                return None
            return cls._optional_int(token_usage.get("output_tokens"))

        return None

    async def launch_job(self, request: LaunchJobRequest) -> JobProgress:
        input_path = resolve_input_path(self.settings, request.input_path)
        pdf_files = expand_pdf_inputs(input_path)
        if not pdf_files:
            raise ValueError(f"No PDF files found at input path: {input_path}")

        descriptors = describe_pdfs(pdf_files)

        job_id = request.job_id.strip() if request.job_id else None
        if not job_id:
            job_id = build_job_id(request.title, str(input_path))

        title = request.title.strip() if request.title else job_id

        self.layout.ensure_job(
            job_id,
            {
                "job_id": job_id,
                "title": title,
                "input_path": self._to_project_relative_path(input_path),
                "created_at": datetime.now(UTC).isoformat(),
                "prompt": request.prompt,
                "models": [
                    {k: v for k, v in model.model_dump().items() if k != "api_key"}
                    for model in request.models
                ],
            },
        )

        run_contexts: list[_RunContext] = []
        total_pages_per_model = sum(descriptor.page_count for descriptor in descriptors)

        for idx, spec in enumerate(request.models):
            self.layout.ensure_model(
                job_id,
                spec.model,
                {
                    "model": spec.model,
                    "mode": spec.mode.value,
                    "provider": spec.provider,
                    "base_url": spec.base_url,
                },
            )

            run_paths = self.layout.prepare_run(
                job_id,
                spec.model,
                {
                    "model": spec.model,
                    "mode": spec.mode.value,
                    "provider": spec.provider,
                    "base_url": spec.base_url,
                    "api_key_env": spec.api_key_env,
                    "tensor_parallel_size": spec.tensor_parallel_size,
                    "data_parallel_size": spec.data_parallel_size,
                    "gpu_memory_utilization": spec.gpu_memory_utilization,
                    "max_model_len": spec.max_model_len,
                    "max_concurrent_requests": spec.max_concurrent_requests,
                    "extra_vllm_args": spec.extra_vllm_args,
                    "created_at": datetime.now(UTC).isoformat(),
                    "source_files": [str(descriptor.path) for descriptor in descriptors],
                    "total_pages": total_pages_per_model,
                },
            )

            run = ModelRunProgress(
                run_id=f"{run_paths.model_slug}:{run_paths.run_number}",
                model=spec.model,
                mode=spec.mode,
                output_dir=str(run_paths.run_dir),
                source_files=[str(descriptor.path) for descriptor in descriptors],
                total_pages=total_pages_per_model,
            )

            run_contexts.append(_RunContext(run_paths=run_paths, run=run, spec_index=idx))

        job = JobProgress(
            job_id=job_id,
            title=title,
            input_path=str(input_path),
            prompt=request.prompt,
            total_pages_all_models=total_pages_per_model * len(request.models),
            models=[context.run for context in run_contexts],
            metadata_path=str(self.layout.job_metadata_path(job_id)),
        )

        cancel_event = threading.Event()

        with self._state_lock:
            existing_job = self._jobs.get(job_id)
            if existing_job and existing_job.status in {
                RunStatus.QUEUED,
                RunStatus.WAITING_RESOURCES,
                RunStatus.RUNNING,
            }:
                raise ValueError(f"Job id already exists and is active: {job_id}")

            if existing_job:
                old_contexts = self._job_contexts.get(job_id, [])
                for old_context in old_contexts:
                    self._run_metrics.pop(self._run_metrics_key(job_id, old_context.run.run_id), None)
                self._jobs.pop(job_id, None)
                self._job_contexts.pop(job_id, None)
                self._cancel_events.pop(job_id, None)
                self._tasks.pop(job_id, None)

            self._jobs[job_id] = job
            self._job_contexts[job_id] = run_contexts
            self._cancel_events[job_id] = cancel_event
            for context in run_contexts:
                self._run_metrics[self._run_metrics_key(job_id, context.run.run_id)] = self._new_metrics()

        loop = asyncio.get_running_loop()
        task = loop.create_task(self._run_job(job_id, request, descriptors))

        with self._state_lock:
            self._tasks[job_id] = task

        return self._jobs[job_id].model_copy(deep=True)

    async def _run_job(
        self,
        job_id: str,
        request: LaunchJobRequest,
        descriptors: list[PDFDescriptor],
    ) -> None:
        with self._state_lock:
            job = self._jobs[job_id]
            job.status = RunStatus.RUNNING
            job.started_at = datetime.now(UTC)
            self._persist_job_metadata(job_id)

            contexts = list(self._job_contexts[job_id])
            cancel_event = self._cancel_events[job_id]

        tasks = [
            asyncio.to_thread(
                self._run_single_model,
                job_id,
                request,
                descriptors,
                context,
                cancel_event,
            )
            for context in contexts
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        with self._state_lock:
            job = self._jobs[job_id]
            if cancel_event.is_set() and all(run.status == RunStatus.CANCELED for run in job.models):
                job.status = RunStatus.CANCELED
            elif any(run.status == RunStatus.FAILED for run in job.models):
                if any(run.status == RunStatus.COMPLETED for run in job.models):
                    job.status = RunStatus.COMPLETED
                else:
                    job.status = RunStatus.FAILED
            elif all(run.status == RunStatus.COMPLETED for run in job.models):
                job.status = RunStatus.COMPLETED
            elif any(run.status == RunStatus.RUNNING for run in job.models):
                job.status = RunStatus.RUNNING
            else:
                job.status = RunStatus.FAILED

            job.ended_at = datetime.now(UTC)
            self._persist_job_metadata(job_id)

    def _resolve_api_auth(self, spec) -> EndpointAuth:
        base_url = spec.base_url
        api_key_env = spec.api_key_env

        if spec.provider and spec.provider in PRESET_BY_KEY:
            preset = PRESET_BY_KEY[spec.provider]
            base_url = base_url or preset.base_url
            api_key_env = api_key_env or preset.api_key_env

        if not base_url:
            raise RuntimeError(f"Missing base_url for API model: {spec.model}")

        api_key = OpenAICompatibleOCRClient.resolve_api_key(spec.api_key, api_key_env)
        return EndpointAuth(base_url=base_url, api_key=api_key)

    def _mark_run_status(self, job_id: str, run_id: str, status: RunStatus, error: str | None = None) -> None:
        with self._state_lock:
            job = self._jobs[job_id]
            for run in job.models:
                if run.run_id == run_id:
                    run.status = status
                    if status == RunStatus.RUNNING and not run.started_at:
                        run.started_at = datetime.now(UTC)
                    if status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED}:
                        run.ended_at = datetime.now(UTC)
                    if error:
                        run.error = error
                    break
            self._recompute_job_progress(job_id)

    @staticmethod
    def _run_runtime_seconds(run: ModelRunProgress) -> float:
        if not run.started_at:
            return 0.0
        end = run.ended_at or datetime.now(UTC)
        return max(0.0, (end - run.started_at).total_seconds())

    def run_runtime_seconds(self, run: ModelRunProgress) -> float:
        return self._run_runtime_seconds(run)

    def estimate_run_eta_seconds(self, run: ModelRunProgress) -> float | None:
        if run.completed_pages <= 0 or not run.started_at:
            return None
        runtime = self._run_runtime_seconds(run)
        rate = run.completed_pages / max(runtime, 1e-6)
        remaining = max(0, run.total_pages - run.completed_pages)
        if rate <= 0:
            return None
        return remaining / rate

    def run_statistics(self, job_id: str, run_id: str) -> dict[str, Any]:
        return self._run_statistics(job_id, run_id)

    def job_statistics(self, job_id: str) -> dict[str, Any]:
        with self._state_lock:
            job = self._jobs.get(job_id)
            if not job:
                return self._finalize_metrics(self._new_metrics(), runtime_seconds=0.0)
            return self._job_statistics(job)

    def _persist_job_metadata(self, job_id: str) -> None:
        job = self._jobs[job_id]

        payload = {
            "job_id": job.job_id,
            "title": job.title,
            "input_path": self._to_project_relative_path(job.input_path),
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            "prompt": job.prompt,
            "total_pages_all_models": job.total_pages_all_models,
            "completed_pages_all_models": job.completed_pages_all_models,
            "progress_ratio": job.progress_ratio(),
            "models": [self._serialize_run_for_job_metadata(run) for run in job.models],
            "statistics": self._job_statistics(job),
        }
        write_json(Path(job.metadata_path), payload)

    def _persist_run_metadata(
        self,
        job_id: str,
        run_paths: RunPaths,
        run: ModelRunProgress,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "run_id": run.run_id,
            "model": run.model,
            "mode": run.mode.value,
            "status": run.status.value,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            "error": run.error,
            "total_pages": run.total_pages,
            "completed_pages": run.completed_pages,
            "source_files": run.source_files,
            "output_dir": run.output_dir,
            "runtime_seconds": self._run_runtime_seconds(run),
            "statistics": self._run_statistics(job_id, run.run_id),
        }
        if extra:
            payload.update(extra)
        write_json(run_paths.run_metadata_path, payload)

    def _append_error(self, run_dir: Path, record: dict[str, Any]) -> None:
        error_path = run_dir / "errors.jsonl"
        with error_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    @staticmethod
    def _read_json_if_exists(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def _persist_pdf_metadata(
        self,
        *,
        pdf_metadata_path: Path,
        source_pdf: Path,
        pdf_slug: str,
        page_count: int,
        pages: list[dict[str, Any]],
        started_at: datetime | None,
        ended_at: datetime | None,
    ) -> None:
        existing = self._read_json_if_exists(pdf_metadata_path)
        created_at = existing.get("created_at") or datetime.now(UTC).isoformat()
        payload = {
            "source_pdf": str(source_pdf),
            "pdf_slug": pdf_slug,
            "page_count": page_count,
            "created_at": created_at,
            "updated_at": datetime.now(UTC).isoformat(),
            "started_at": started_at.isoformat() if started_at else existing.get("started_at"),
            "ended_at": ended_at.isoformat() if ended_at else None,
            "statistics": self._pdf_statistics(page_count=page_count, pages=pages),
            "pages": sorted(pages, key=lambda entry: int(entry.get("page_number", 0))),
        }
        write_json(pdf_metadata_path, payload)

    @staticmethod
    def _process_page_ocr_request(
        *,
        client: OpenAICompatibleOCRClient,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        page_number: int,
        image_png: bytes,
    ) -> _PageOCROutcome:
        page_started_at = datetime.now(UTC)
        ocr_result: OCRPageResult | None = None
        usage_payload: dict[str, Any] | None = None
        finish_reason: str | None = None
        provider_model: str | None = None
        attempts = 0
        request_seconds: float | None = None
        error_text: str | None = None

        try:
            ocr_result = client.ocr_page(
                model=model,
                image_png=image_png,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            markdown_text = ocr_result.markdown
            usage_payload = ocr_result.usage
            finish_reason = ocr_result.finish_reason
            provider_model = ocr_result.provider_model
            attempts = ocr_result.attempts
            request_seconds = ocr_result.request_duration_seconds
        except Exception as exc:  # noqa: BLE001
            error_text = str(exc)
            markdown_text = f"<!-- OCR failed for page {page_number}: {error_text} -->\n"

        page_ended_at = datetime.now(UTC)
        processing_seconds = max(0.0, (page_ended_at - page_started_at).total_seconds())
        return _PageOCROutcome(
            page_number=page_number,
            markdown_text=markdown_text,
            usage_payload=usage_payload,
            finish_reason=finish_reason,
            provider_model=provider_model,
            attempts=attempts,
            request_seconds=request_seconds,
            error_text=error_text,
            page_started_at=page_started_at,
            page_ended_at=page_ended_at,
            processing_seconds=processing_seconds,
        )

    def _run_single_model(
        self,
        job_id: str,
        request: LaunchJobRequest,
        descriptors: list[PDFDescriptor],
        context: _RunContext,
        cancel_event: threading.Event,
    ) -> None:
        with self._state_lock:
            spec = request.models[context.spec_index]
            run = self._get_run(job_id, context.run.run_id)
            if run is None:
                return

        self._persist_run_metadata(job_id, context.run_paths, context.run)

        local_handle: ServerHandle | None = None
        client: OpenAICompatibleOCRClient | None = None

        try:
            if spec.mode == ModelMode.LOCAL:
                self._mark_run_status(job_id, run.run_id, RunStatus.WAITING_RESOURCES)

                local_handle = self.vllm_manager.acquire_server(
                    model=spec.model,
                    tensor_parallel_size=spec.tensor_parallel_size,
                    data_parallel_size=spec.data_parallel_size or self.settings.vllm_data_parallel_size,
                    gpu_memory_utilization=(
                        spec.gpu_memory_utilization or self.settings.vllm_gpu_memory_utilization
                    ),
                    max_model_len=spec.max_model_len or self.settings.vllm_max_model_len,
                    extra_vllm_args=spec.extra_vllm_args,
                    cancel_event=cancel_event,
                )
                auth = EndpointAuth(base_url=local_handle.base_url, api_key="EMPTY")
            else:
                auth = self._resolve_api_auth(spec)

            client = OpenAICompatibleOCRClient(auth)
            self._mark_run_status(job_id, run.run_id, RunStatus.RUNNING)

            max_concurrent_requests = spec.max_concurrent_requests or self.settings.vllm_max_concurrent_requests
            max_concurrent_requests = max(1, int(max_concurrent_requests))

            for descriptor in descriptors:
                if cancel_event.is_set():
                    self._mark_run_status(job_id, run.run_id, RunStatus.CANCELED)
                    self._persist_run_metadata(job_id, context.run_paths, run)
                    return

                pdf_layout = self.layout.prepare_pdf(
                    run_dir=context.run_paths.run_dir,
                    source_pdf=descriptor.path,
                    page_count=descriptor.page_count,
                )
                pdf_started_at = datetime.now(UTC)
                pdf_pages: list[dict[str, Any]] = []
                self._persist_pdf_metadata(
                    pdf_metadata_path=pdf_layout.pdf_metadata_path,
                    source_pdf=descriptor.path,
                    pdf_slug=pdf_layout.pdf_slug,
                    page_count=descriptor.page_count,
                    pages=pdf_pages,
                    started_at=pdf_started_at,
                    ended_at=None,
                )

                with self._state_lock:
                    run.current_pdf = str(descriptor.path)
                    run.current_page = 0
                    self._persist_run_metadata(job_id, context.run_paths, run)
                    self._persist_job_metadata(job_id)

                page_iter = iter_rendered_pages(descriptor.path)
                page_iter_exhausted = False
                pending: dict[concurrent.futures.Future[_PageOCROutcome], int] = {}

                with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_requests) as executor:
                    while True:
                        while not cancel_event.is_set() and not page_iter_exhausted and len(pending) < max_concurrent_requests:
                            try:
                                page_number, image_png = next(page_iter)
                            except StopIteration:
                                page_iter_exhausted = True
                                break
                            pending[
                                executor.submit(
                                    self._process_page_ocr_request,
                                    client=client,
                                    model=spec.model,
                                    prompt=request.prompt,
                                    max_tokens=request.max_tokens,
                                    temperature=request.temperature,
                                    page_number=page_number,
                                    image_png=image_png,
                                )
                            ] = page_number

                        if not pending:
                            if page_iter_exhausted or cancel_event.is_set():
                                break
                            continue

                        done, _ = concurrent.futures.wait(
                            pending.keys(),
                            return_when=concurrent.futures.FIRST_COMPLETED,
                        )

                        for future in done:
                            page_number = pending.pop(future)
                            try:
                                outcome = future.result()
                            except Exception as exc:  # noqa: BLE001
                                now = datetime.now(UTC)
                                outcome = _PageOCROutcome(
                                    page_number=page_number,
                                    markdown_text=f"<!-- OCR failed for page {page_number}: {exc} -->\n",
                                    usage_payload=None,
                                    finish_reason=None,
                                    provider_model=None,
                                    attempts=0,
                                    request_seconds=None,
                                    error_text=str(exc),
                                    page_started_at=now,
                                    page_ended_at=now,
                                    processing_seconds=0.0,
                                )

                            if outcome.error_text is not None:
                                self._append_error(
                                    context.run_paths.run_dir,
                                    {
                                        "timestamp": datetime.now(UTC).isoformat(),
                                        "source_pdf": str(descriptor.path),
                                        "page": outcome.page_number,
                                        "error": outcome.error_text,
                                    },
                                )

                            token_usage = self._token_usage_from_provider_usage(outcome.usage_payload)
                            page_path = self.layout.write_page_markdown(
                                pdf_layout.pdf_dir,
                                outcome.page_number,
                                outcome.markdown_text,
                            )
                            try:
                                output_bytes = page_path.stat().st_size
                            except OSError:
                                output_bytes = len(outcome.markdown_text.encode("utf-8"))

                            page_record = {
                                "page_number": outcome.page_number,
                                "status": "completed" if outcome.error_text is None else "failed",
                                "started_at": outcome.page_started_at.isoformat(),
                                "ended_at": outcome.page_ended_at.isoformat(),
                                "processing_time_seconds": outcome.processing_seconds,
                                "ocr_request_time_seconds": outcome.request_seconds,
                                "attempts": outcome.attempts,
                                "finish_reason": outcome.finish_reason,
                                "provider_model": outcome.provider_model,
                                "token_usage": token_usage,
                                "usage": outcome.usage_payload,
                                "output_markdown_file": page_path.name,
                                "output_markdown_path": str(page_path),
                                "output_bytes": output_bytes,
                                "error": outcome.error_text,
                            }
                            pdf_pages.append(page_record)
                            self._persist_pdf_metadata(
                                pdf_metadata_path=pdf_layout.pdf_metadata_path,
                                source_pdf=descriptor.path,
                                pdf_slug=pdf_layout.pdf_slug,
                                page_count=descriptor.page_count,
                                pages=pdf_pages,
                                started_at=pdf_started_at,
                                ended_at=None,
                            )
                            self._record_run_page_metrics(
                                job_id=job_id,
                                run_id=run.run_id,
                                succeeded=outcome.error_text is None,
                                processing_time_seconds=outcome.processing_seconds,
                                ocr_request_time_seconds=outcome.request_seconds,
                                token_usage=token_usage,
                            )

                            with self._state_lock:
                                run.current_page = outcome.page_number
                                run.completed_pages += 1
                                self._recompute_job_progress(job_id)
                                self._persist_run_metadata(job_id, context.run_paths, run)
                                self._persist_job_metadata(job_id)

                        if page_iter_exhausted and not pending:
                            break

                self._persist_pdf_metadata(
                    pdf_metadata_path=pdf_layout.pdf_metadata_path,
                    source_pdf=descriptor.path,
                    pdf_slug=pdf_layout.pdf_slug,
                    page_count=descriptor.page_count,
                    pages=pdf_pages,
                    started_at=pdf_started_at,
                    ended_at=datetime.now(UTC),
                )

                if cancel_event.is_set():
                    self._mark_run_status(job_id, run.run_id, RunStatus.CANCELED)
                    self._persist_run_metadata(job_id, context.run_paths, run)
                    return

            with self._state_lock:
                if run.status != RunStatus.CANCELED:
                    run.status = RunStatus.COMPLETED
                    run.ended_at = datetime.now(UTC)
                self._recompute_job_progress(job_id)
                self._persist_run_metadata(job_id, context.run_paths, run)
                self._persist_job_metadata(job_id)

        except Exception as exc:  # noqa: BLE001
            with self._state_lock:
                run = self._get_run(job_id, context.run.run_id)
                if run:
                    run.status = RunStatus.FAILED
                    run.error = str(exc)
                    run.ended_at = datetime.now(UTC)
                    self._recompute_job_progress(job_id)
                    self._persist_run_metadata(job_id, context.run_paths, run)
                    self._persist_job_metadata(job_id)
        finally:
            if client:
                client.close()
            if local_handle:
                self.vllm_manager.release_server(local_handle)

    def _get_run(self, job_id: str, run_id: str) -> ModelRunProgress | None:
        job = self._jobs.get(job_id)
        if not job:
            return None
        for run in job.models:
            if run.run_id == run_id:
                return run
        return None

    def _recompute_job_progress(self, job_id: str) -> None:
        job = self._jobs[job_id]
        job.completed_pages_all_models = sum(run.completed_pages for run in job.models)

    def list_jobs(self) -> list[JobProgress]:
        with self._state_lock:
            return [job.model_copy(deep=True) for job in self._jobs.values()]

    def get_job(self, job_id: str) -> JobProgress | None:
        with self._state_lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return job.model_copy(deep=True)

    def list_output_pages(self, job_id: str) -> list[dict[str, Any]]:
        job_dir = self.layout.job_dir(job_id)
        if not job_dir.exists() or not job_dir.is_dir():
            raise FileNotFoundError(f"Job outputs not found for {job_id}")

        pages: list[dict[str, Any]] = []
        model_dirs = sorted((path for path in job_dir.iterdir() if path.is_dir()), key=lambda path: path.name)

        for model_dir in model_dirs:
            model_slug = model_dir.name
            run_dirs = sorted(
                (
                    path
                    for path in model_dir.iterdir()
                    if path.is_dir() and self.layout.parse_run_number(path.name) is not None
                ),
                key=lambda path: int(self.layout.parse_run_number(path.name) or 0),
            )

            for run_dir in run_dirs:
                run_number = int(self.layout.parse_run_number(run_dir.name) or 0)
                run_metadata = self._read_json_if_exists(run_dir / "run_metadata.json")
                model_name = str(run_metadata.get("model") or model_slug)
                mode = run_metadata.get("mode")

                pdf_dirs = sorted((path for path in run_dir.iterdir() if path.is_dir()), key=lambda path: path.name)
                for pdf_dir in pdf_dirs:
                    pdf_slug = pdf_dir.name
                    pdf_metadata = self._read_json_if_exists(pdf_dir / "pdf_metadata.json")
                    source_pdf = pdf_metadata.get("source_pdf")

                    page_files = sorted(
                        (
                            path
                            for path in pdf_dir.glob("*.md")
                            if path.is_file() and path.stem.isdigit()
                        ),
                        key=lambda path: int(path.stem),
                    )
                    for page_file in page_files:
                        page_number = int(page_file.stem)
                        output_tokens = self._output_tokens_from_pdf_metadata(pdf_metadata, page_number)
                        pages.append(
                            {
                                "index": -1,
                                "model": model_name,
                                "model_slug": model_slug,
                                "mode": mode,
                                "run_number": run_number,
                                "pdf_slug": pdf_slug,
                                "page_number": page_number,
                                "source_pdf": source_pdf,
                                "markdown_path": str(page_file),
                                "bytes": page_file.stat().st_size,
                                "output_tokens": output_tokens,
                            }
                        )

        pages.sort(
            key=lambda item: (
                str(item["model_slug"]),
                int(item["run_number"]),
                str(item["pdf_slug"]),
                int(item["page_number"]),
            )
        )
        for index, item in enumerate(pages):
            item["index"] = index
        return pages

    def get_output_page(self, job_id: str, page_index: int) -> dict[str, Any]:
        pages = self.list_output_pages(job_id)
        if page_index < 0 or page_index >= len(pages):
            raise IndexError(f"Page index out of range: {page_index}")

        page = dict(pages[page_index])
        markdown_path = Path(str(page["markdown_path"]))
        markdown = markdown_path.read_text(encoding="utf-8")
        page["output_characters"] = len(markdown)
        if page.get("output_tokens") is None:
            pdf_metadata = self._read_json_if_exists(markdown_path.parent / "pdf_metadata.json")
            page_number = self._optional_int(page.get("page_number"))
            if page_number is not None:
                page["output_tokens"] = self._output_tokens_from_pdf_metadata(pdf_metadata, page_number)
        return {"page": page, "markdown": markdown}

    def dismiss_job(self, job_id: str) -> tuple[bool, str | None]:
        with self._state_lock:
            job = self._jobs.get(job_id)
            if not job:
                return False, "job not found"

            if job.status not in {RunStatus.COMPLETED, RunStatus.CANCELED}:
                return False, "only completed or canceled jobs can be dismissed"

            task = self._tasks.get(job_id)
            if task and not task.done():
                return False, "job is still running"

            contexts = self._job_contexts.pop(job_id, [])
            for context in contexts:
                self._run_metrics.pop(self._run_metrics_key(job_id, context.run.run_id), None)

            self._jobs.pop(job_id, None)
            self._cancel_events.pop(job_id, None)
            self._tasks.pop(job_id, None)
            return True, None

    def cancel_job(self, job_id: str) -> bool:
        with self._state_lock:
            cancel_event = self._cancel_events.get(job_id)
            if not cancel_event:
                return False
            cancel_event.set()
            job = self._jobs.get(job_id)
            if job and job.status not in {RunStatus.COMPLETED, RunStatus.FAILED}:
                job.status = RunStatus.CANCELED
                self._persist_job_metadata(job_id)
            return True

    def job_runtime_seconds(self, job: JobProgress) -> float:
        if not job.started_at:
            return 0.0
        end = job.ended_at or datetime.now(UTC)
        return max(0.0, (end - job.started_at).total_seconds())

    def estimate_eta_seconds(self, job: JobProgress) -> float | None:
        if job.completed_pages_all_models <= 0 or not job.started_at:
            return None
        runtime = self.job_runtime_seconds(job)
        rate = job.completed_pages_all_models / max(runtime, 1e-6)
        remaining = max(0, job.total_pages_all_models - job.completed_pages_all_models)
        if rate <= 0:
            return None
        return remaining / rate

    async def shutdown(self) -> None:
        tasks: list[asyncio.Task[None]]
        with self._state_lock:
            for event in self._cancel_events.values():
                event.set()
            tasks = [task for task in self._tasks.values() if not task.done()]

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.vllm_manager.shutdown_all()

    def resolve_provider_key_status(self, provider_key: str, env_var_name: str | None) -> dict[str, Any]:
        resolved_env = env_var_name
        if provider_key in PRESET_BY_KEY and not resolved_env:
            resolved_env = PRESET_BY_KEY[provider_key].api_key_env

        present = bool(OpenAICompatibleOCRClient.lookup_api_key_env(resolved_env))
        return {
            "provider": provider_key,
            "api_key_env": resolved_env,
            "present": present,
        }

    def gpu_stats(self) -> dict[str, Any]:
        return self.vllm_manager.gpu_payload()
