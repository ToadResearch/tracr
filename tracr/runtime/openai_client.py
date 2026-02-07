from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from openai import OpenAI
from openai import APIConnectionError, APIStatusError, APITimeoutError


@dataclass
class EndpointAuth:
    base_url: str
    api_key: str


@dataclass
class OCRPageResult:
    markdown: str
    request_duration_seconds: float
    usage: dict[str, Any] | None
    finish_reason: str | None
    provider_model: str | None
    attempts: int


class OpenAICompatibleOCRClient:
    def __init__(self, auth: EndpointAuth, timeout_seconds: float = 300.0):
        self.auth = auth
        self.client = OpenAI(
            api_key=auth.api_key,
            base_url=auth.base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )

    @staticmethod
    def lookup_api_key_env(api_key_env: str | None) -> str | None:
        if not api_key_env:
            return None

        env_value = os.getenv(api_key_env)
        if env_value:
            return env_value

        env_path = Path(__file__).resolve().parents[2] / ".env"
        try:
            env_map = dotenv_values(env_path)
        except Exception:  # noqa: BLE001
            return None

        fallback = env_map.get(api_key_env)
        if isinstance(fallback, str) and fallback.strip():
            return fallback
        return None

    @staticmethod
    def resolve_api_key(api_key: str | None, api_key_env: str | None) -> str:
        if api_key:
            return api_key
        if api_key_env:
            env_value = OpenAICompatibleOCRClient.lookup_api_key_env(api_key_env)
            if env_value:
                return env_value
        raise RuntimeError(
            f"Missing API key. Set inline key or environment variable: {api_key_env or '<unset>'}"
        )

    @staticmethod
    def _image_content_block(image_png: bytes) -> dict[str, Any]:
        encoded = base64.b64encode(image_png).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{encoded}"},
        }

    def ocr_page(
        self,
        *,
        model: str,
        image_png: bytes,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        retries: int = 4,
    ) -> OCRPageResult:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    self._image_content_block(image_png),
                ],
            }
        ]

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                started = time.perf_counter()
                completion = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                duration = max(0.0, time.perf_counter() - started)
                content = completion.choices[0].message.content
                usage = completion.usage.model_dump() if completion.usage else None
                finish_reason = completion.choices[0].finish_reason if completion.choices else None
                provider_model = getattr(completion, "model", None)
                return OCRPageResult(
                    markdown=(content or "").strip(),
                    request_duration_seconds=duration,
                    usage=usage,
                    finish_reason=finish_reason,
                    provider_model=provider_model,
                    attempts=attempt,
                )
            except (APIConnectionError, APITimeoutError) as exc:
                last_error = exc
            except APIStatusError as exc:
                last_error = exc
                if exc.status_code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                    raise

            if attempt < retries:
                time.sleep(min(2**attempt, 15))

        if last_error:
            raise RuntimeError(
                f"OCR request failed for model '{model}' against '{self.auth.base_url}': {last_error}"
            ) from last_error
        raise RuntimeError("OCR request failed without a concrete error")

    def ocr_page_markdown(
        self,
        *,
        model: str,
        image_png: bytes,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        retries: int = 4,
    ) -> str:
        return self.ocr_page(
            model=model,
            image_png=image_png,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            retries=retries,
        ).markdown

    def raw_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        completion = self.client.chat.completions.create(**payload)
        return completion.model_dump()

    def close(self) -> None:
        self.client.close()
