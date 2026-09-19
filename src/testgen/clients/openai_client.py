"""OpenAI API client with exponential backoff and token/cost tracking."""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path

from testgen.clients.base import LLMClient, LLMError
from testgen.models import LLMResponse


class OpenAIClient(LLMClient):
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        api_key: str | None = None,
        cache_dir: str | Path | None = None,
    ):
        # Import here to keep it optional at import time
        from openai import OpenAI
        self.model = model
        self._cache_dir = Path(cache_dir) if cache_dir else None
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

        kwargs: dict = {}
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        self._client = OpenAI(**kwargs)

    def _cache_key(self, messages: list[dict], temperature: float) -> str:
        blob = json.dumps({"messages": messages, "model": self.model, "temperature": temperature}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    def _cache_get(self, key: str) -> str | None:
        if not self._cache_dir:
            return None
        p = self._cache_dir / f"{key}.txt"
        return p.read_text(encoding="utf-8") if p.exists() else None

    def _cache_put(self, key: str, text: str) -> None:
        if self._cache_dir:
            (self._cache_dir / f"{key}.txt").write_text(text, encoding="utf-8")

    def generate(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 2048) -> LLMResponse:
        from openai import APIError, APITimeoutError, RateLimitError

        # Check cache first
        key = self._cache_key(messages, temperature)
        cached = self._cache_get(key)
        if cached is not None:
            return LLMResponse(text=cached, model=self.model + ":cached",
                               prompt_tokens=0, completion_tokens=0, latency_ms=0.0)

        # Exponential backoff: 3 retries
        last_exc: Exception | None = None
        for attempt in range(3):
            start = time.monotonic()
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                break
            except (APITimeoutError, RateLimitError) as e:
                last_exc = e
                wait = 2 ** attempt
                time.sleep(wait)
            except APIError as e:
                raise LLMError(str(e)) from e
        else:
            raise LLMError(f"API failed after 3 attempts: {last_exc}") from last_exc

        latency_ms = (time.monotonic() - start) * 1000
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        self._cache_put(key, text)
        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency_ms,
        )
