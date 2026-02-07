from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


DEFAULT_OCR_PROMPT = (
    "You are an OCR assistant. Extract all visible text from this PDF page and return clean markdown. "
    "Preserve headings, lists, and tables when possible. Do not add commentary."
)


class ModelMode(str, Enum):
    API = "api"
    LOCAL = "local"


class RunStatus(str, Enum):
    QUEUED = "queued"
    WAITING_RESOURCES = "waiting_resources"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class OCRModelSpec(BaseModel):
    model: str = Field(..., description="Model id, e.g. org/model-name")
    mode: ModelMode

    provider: str | None = Field(default=None, description="Provider preset key for API mode")
    base_url: str | None = Field(default=None, description="OpenAI-compatible base URL for API mode")
    api_key_env: str | None = Field(default=None, description="Environment key name for API key lookup")
    api_key: str | None = Field(default=None, description="Direct API key override")

    tensor_parallel_size: int = Field(default=1, ge=1, description="Local mode tensor parallel GPUs")
    data_parallel_size: int | None = Field(default=None, ge=1, description="Local mode data parallel groups")
    gpu_memory_utilization: float | None = Field(default=None, gt=0.0, le=1.0)
    max_model_len: int | None = Field(default=None, ge=1)
    max_concurrent_requests: int | None = Field(default=None, ge=1, description="Max in-flight OCR requests")
    extra_vllm_args: list[str] = Field(default_factory=list, description="Extra local vLLM serve CLI args")

    @model_validator(mode="after")
    def validate_api_mode(self) -> "OCRModelSpec":
        if self.mode == ModelMode.API and not self.base_url:
            raise ValueError("API model requires base_url")
        self.extra_vllm_args = [arg.strip() for arg in self.extra_vllm_args if arg and arg.strip()]
        return self


class LaunchJobRequest(BaseModel):
    job_id: str | None = Field(default=None, description="Stable job id; if omitted a slug is generated")
    title: str | None = Field(default=None)
    input_path: str = Field(..., description="PDF file path or directory path")

    models: list[OCRModelSpec] = Field(default_factory=list)
    prompt: str = Field(default=DEFAULT_OCR_PROMPT)
    max_tokens: int = Field(default=2048, ge=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    @field_validator("models")
    @classmethod
    def validate_models(cls, value: list[OCRModelSpec]) -> list[OCRModelSpec]:
        if not value:
            raise ValueError("At least one model is required")
        return value


class CancelJobResponse(BaseModel):
    job_id: str
    canceled: bool


class DismissJobResponse(BaseModel):
    job_id: str
    dismissed: bool


class PDFProgress(BaseModel):
    source_pdf: str
    page_count: int
    pages_completed: int = 0


class ModelRunProgress(BaseModel):
    run_id: str
    model: str
    mode: ModelMode
    status: RunStatus = RunStatus.QUEUED
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None

    total_pages: int = 0
    completed_pages: int = 0
    current_pdf: str | None = None
    current_page: int | None = None

    output_dir: str
    source_files: list[str] = Field(default_factory=list)
    runtime_seconds: float = 0.0
    eta_seconds: float | None = None
    statistics: dict[str, Any] = Field(default_factory=dict)

    def progress_ratio(self) -> float:
        if self.total_pages <= 0:
            return 0.0
        return min(1.0, self.completed_pages / self.total_pages)


class JobProgress(BaseModel):
    job_id: str
    title: str
    input_path: str
    status: RunStatus = RunStatus.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    ended_at: datetime | None = None
    prompt: str = DEFAULT_OCR_PROMPT

    total_pages_all_models: int = 0
    completed_pages_all_models: int = 0

    models: list[ModelRunProgress] = Field(default_factory=list)
    metadata_path: str
    runtime_seconds: float = 0.0
    eta_seconds: float | None = None
    statistics: dict[str, Any] = Field(default_factory=dict)

    def progress_ratio(self) -> float:
        if self.total_pages_all_models <= 0:
            return 0.0
        return min(1.0, self.completed_pages_all_models / self.total_pages_all_models)


class InputCandidate(BaseModel):
    path: str
    kind: str
    relative_to_inputs: str


class LaunchJobResponse(BaseModel):
    job: JobProgress


class ListJobsResponse(BaseModel):
    jobs: list[JobProgress]


class ProviderPresetResponse(BaseModel):
    key: str
    label: str
    base_url: str
    api_key_env: str
    notes: str
    example_models: list[str] = Field(default_factory=list)


class SystemGPUStats(BaseModel):
    gpu_count: int
    gpus: list[dict[str, Any]]


class JobOutputPageSummary(BaseModel):
    index: int
    model: str
    model_slug: str
    mode: str | None = None
    run_number: int
    pdf_slug: str
    page_number: int
    source_pdf: str | None = None
    markdown_path: str
    bytes: int
    output_tokens: int | None = None
    output_characters: int | None = None


class JobOutputPagesResponse(BaseModel):
    job_id: str
    pages: list[JobOutputPageSummary]


class JobOutputPageContentResponse(BaseModel):
    job_id: str
    page: JobOutputPageSummary
    markdown: str


class OutputTreeEntryResponse(BaseModel):
    name: str
    relative_path: str
    kind: str
    size_bytes: int | None = None
    is_metadata_json: bool = False
    is_markdown: bool = False


class OutputTreeResponse(BaseModel):
    outputs_root: str
    current_path: str
    parent_path: str | None = None
    entries: list[OutputTreeEntryResponse]


class OutputFileResponse(BaseModel):
    relative_path: str
    name: str
    extension: str
    size_bytes: int
    content: str
    output_tokens: int | None = None
    output_characters: int | None = None


def iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def as_path(value: str | Path) -> Path:
    if isinstance(value, Path):
        return value
    return Path(value)
