from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    api_host: str = Field(default="0.0.0.0", alias="OCR_API_HOST")
    api_port: int = Field(default=8787, alias="OCR_API_PORT")
    api_base_url: str = Field(default="http://127.0.0.1:8787", alias="OCR_API_BASE_URL")
    web_host: str = Field(default="127.0.0.1", alias="OCR_WEB_HOST")
    web_port: int = Field(default=8790, alias="OCR_WEB_PORT")

    inputs_dir: str = Field(default="inputs", alias="OCR_INPUTS_DIR")
    outputs_dir: str = Field(default="outputs", alias="OCR_OUTPUTS_DIR")
    job_configs_dir: str = Field(default="job_configs", alias="OCR_JOB_CONFIGS_DIR")
    state_dir: str = Field(default=".ocr_state", alias="OCR_STATE_DIR")

    default_upstream_base_url: str | None = Field(default=None, alias="OCR_DEFAULT_UPSTREAM_BASE_URL")
    default_upstream_api_key: str | None = Field(default=None, alias="OCR_DEFAULT_UPSTREAM_API_KEY")

    vllm_base_port: int = Field(default=9000, alias="OCR_VLLM_BASE_PORT")
    vllm_gpu_memory_utilization: float = Field(default=0.90, alias="OCR_VLLM_GPU_MEMORY_UTILIZATION")
    vllm_max_model_len: int | None = Field(default=None, alias="OCR_VLLM_MAX_MODEL_LEN")
    vllm_data_parallel_size: int = Field(default=1, ge=1, alias="OCR_VLLM_DATA_PARALLEL_SIZE")
    vllm_max_concurrent_requests: int = Field(default=8, ge=1, alias="OCR_VLLM_MAX_CONCURRENT_REQUESTS")
    local_max_concurrent_models: int = Field(default=8, alias="OCR_LOCAL_MAX_CONCURRENT_MODELS")

    def resolve_path(self, path_value: str) -> Path:
        candidate = Path(path_value).expanduser()
        if candidate.is_absolute():
            return candidate
        return REPO_ROOT / candidate

    @property
    def inputs_path(self) -> Path:
        return self.resolve_path(self.inputs_dir)

    @property
    def outputs_path(self) -> Path:
        return self.resolve_path(self.outputs_dir)

    @property
    def job_configs_path(self) -> Path:
        return self.resolve_path(self.job_configs_dir)

    @property
    def state_path(self) -> Path:
        return self.resolve_path(self.state_dir)

    def ensure_runtime_dirs(self) -> None:
        self.inputs_path.mkdir(parents=True, exist_ok=True)
        self.outputs_path.mkdir(parents=True, exist_ok=True)
        self.job_configs_path.mkdir(parents=True, exist_ok=True)
        self.state_path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_runtime_dirs()
    return settings
