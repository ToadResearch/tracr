from tracr.core.config import REPO_ROOT, Settings


def test_empty_optional_int_env_is_ignored(monkeypatch) -> None:
    monkeypatch.setenv("OCR_VLLM_MAX_MODEL_LEN", "")
    settings = Settings(_env_file=None)
    assert settings.vllm_max_model_len is None


def test_repo_root_and_default_inputs_path() -> None:
    settings = Settings(_env_file=None)
    assert (REPO_ROOT / "pyproject.toml").exists()
    assert settings.inputs_path == REPO_ROOT / "inputs"
    assert settings.job_configs_path == REPO_ROOT / "job_configs"
    assert settings.vllm_data_parallel_size == 1
    assert settings.vllm_max_concurrent_requests == 8
