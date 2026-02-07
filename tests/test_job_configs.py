from pathlib import Path

import pytest

from tracr.core.config import Settings
from tracr.core.job_configs import discover_job_configs, load_job_config
from tracr.core.models import ModelMode


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


def test_discover_job_configs_lists_yaml_files(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    (settings.job_configs_path / "a.yaml").write_text("input_path: inputs/a.pdf\nmodels: []\n", encoding="utf-8")
    nested = settings.job_configs_path / "nested"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "b.yml").write_text("input_path: inputs/b.pdf\nmodels: []\n", encoding="utf-8")
    (nested / "ignore.txt").write_text("hello", encoding="utf-8")

    candidates = discover_job_configs(settings)
    relatives = [item["relative_to_configs"] for item in candidates]

    assert "a.yaml" in relatives
    assert "nested/b.yml" in relatives
    assert all(not item.endswith(".txt") for item in relatives)


def test_load_job_config_validates_with_launch_request(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    payload_path = settings.job_configs_path / "batch.yaml"
    payload_path.write_text(
        "\n".join(
            [
                "job_id: compare-a",
                "title: compare run",
                "input_path: inputs/main.pdf",
                "max_tokens: 2048",
                "temperature: 0.0",
                "models:",
                "  - model: gpt-5-mini",
                "    mode: api",
                "    provider: openai",
                "    base_url: https://api.openai.com/v1",
                "    api_key_env: OPENAI_API_KEY",
                "  - model: lightonai/LightOnOCR-2-1B",
                "    mode: local",
                "    tensor_parallel_size: 1",
                "    data_parallel_size: 1",
                "    gpu_memory_utilization: 0.9",
                "    max_model_len: 16384",
                "    max_concurrent_requests: 8",
                "    extra_vllm_args:",
                "      - --enforce-eager",
            ]
        ),
        encoding="utf-8",
    )

    request = load_job_config(settings, "batch.yaml")

    assert request.job_id == "compare-a"
    assert request.input_path == "inputs/main.pdf"
    assert len(request.models) == 2
    assert request.models[0].mode == ModelMode.API
    assert request.models[1].mode == ModelMode.LOCAL
    assert request.models[1].data_parallel_size == 1
    assert request.models[1].max_concurrent_requests == 8
    assert request.models[1].extra_vllm_args == ["--enforce-eager"]


def test_load_job_config_rejects_non_yaml_extension(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    payload_path = settings.job_configs_path / "bad.txt"
    payload_path.write_text("input_path: inputs/main.pdf\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must end in .yaml or .yml"):
        load_job_config(settings, str(payload_path))
