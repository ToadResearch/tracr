from tracr.runtime.openai_client import OpenAICompatibleOCRClient


def test_lookup_api_key_env_prefers_process_env(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "from-process-env")
    value = OpenAICompatibleOCRClient.lookup_api_key_env("GEMINI_API_KEY")
    assert value == "from-process-env"


def test_lookup_api_key_env_falls_back_to_dotenv(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def fake_dotenv_values(_path):
        return {"GEMINI_API_KEY": "from-dotenv"}

    monkeypatch.setattr("tracr.runtime.openai_client.dotenv_values", fake_dotenv_values)

    value = OpenAICompatibleOCRClient.lookup_api_key_env("GEMINI_API_KEY")
    assert value == "from-dotenv"


def test_resolve_api_key_uses_env_lookup(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fake_dotenv_values(_path):
        return {"OPENAI_API_KEY": "dotenv-openai-key"}

    monkeypatch.setattr("tracr.runtime.openai_client.dotenv_values", fake_dotenv_values)

    value = OpenAICompatibleOCRClient.resolve_api_key(None, "OPENAI_API_KEY")
    assert value == "dotenv-openai-key"
