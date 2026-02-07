from tracr.core.provider_presets import PRESET_BY_KEY, PROVIDER_PRESETS


def test_provider_preset_list_and_examples() -> None:
    keys = [preset.key for preset in PROVIDER_PRESETS]

    assert keys == ["openai", "openrouter", "gemini"]
    assert "nvidia_nim" not in keys

    assert PRESET_BY_KEY["openai"].example_models == ("gpt-5.2", "gpt-5-mini")
    assert PRESET_BY_KEY["openrouter"].example_models == ("google/gemini-3-flash-preview",)
    assert PRESET_BY_KEY["gemini"].example_models == ("gemini-3-pro-preview", "gemini-3-flash-preview")
