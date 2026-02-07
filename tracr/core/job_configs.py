from __future__ import annotations

from pathlib import Path

import yaml

from tracr.core.config import Settings
from tracr.core.models import LaunchJobRequest


JOB_CONFIG_SUFFIXES = {".yaml", ".yml"}


def is_job_config(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in JOB_CONFIG_SUFFIXES


def resolve_job_config_path(settings: Settings, candidate: str) -> Path:
    raw = Path(candidate).expanduser()
    if raw.is_absolute():
        return raw

    direct = (Path.cwd() / raw).resolve()
    if direct.exists():
        return direct

    from_configs = (settings.job_configs_path / raw).resolve()
    return from_configs


def discover_job_configs(settings: Settings, max_items: int = 500) -> list[dict[str, str]]:
    configs_root = settings.job_configs_path
    configs_root.mkdir(parents=True, exist_ok=True)

    candidates: list[dict[str, str]] = []
    for path in sorted(configs_root.rglob("*")):
        if len(candidates) >= max_items:
            break
        if not is_job_config(path):
            continue

        candidates.append(
            {
                "path": str(path),
                "relative_to_configs": str(path.relative_to(configs_root)),
            }
        )

    return candidates


def load_job_config(settings: Settings, candidate: str) -> LaunchJobRequest:
    path = resolve_job_config_path(settings, candidate)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Job config file not found: {path}")
    if path.suffix.lower() not in JOB_CONFIG_SUFFIXES:
        raise ValueError("Job config file must end in .yaml or .yml")

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("Job config root must be a mapping/object")

    return LaunchJobRequest.model_validate(payload)
