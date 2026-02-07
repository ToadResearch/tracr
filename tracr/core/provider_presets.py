from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    key: str
    label: str
    base_url: str
    api_key_env: str
    notes: str
    example_models: tuple[str, ...] = ()


PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        key="openai",
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        notes="Official OpenAI endpoint.",
        example_models=("gpt-5.2", "gpt-5-mini"),
    ),
    ProviderPreset(
        key="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        notes="OpenRouter OpenAI-compatible endpoint.",
        example_models=("google/gemini-3-flash-preview",),
    ),
    ProviderPreset(
        key="gemini",
        label="Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        notes="Google Gemini OpenAI-compatible endpoint.",
        example_models=("gemini-3-pro-preview", "gemini-3-flash-preview"),
    ),
)

PRESET_BY_KEY = {preset.key: preset for preset in PROVIDER_PRESETS}


DEFAULT_LOCAL_MODELS: tuple[str, ...] = (
    "lightonai/LightOnOCR-2-1B",
    "zai-org/GLM-OCR",
    "PaddlePaddle/PaddleOCR-VL-1.5",
    "allenai/olmOCR-2-7B-1025",
    "datalab-to/chandra",
)


def model_slug(model_name: str) -> str:
    value = model_name.strip().replace("/", "-")
    value = value.replace(" ", "-")
    while "--" in value:
        value = value.replace("--", "-")
    return value
