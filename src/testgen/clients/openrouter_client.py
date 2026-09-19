"""OpenRouter client: OpenAI-compatible API providing access to free and open-source models."""
from __future__ import annotations
import os
import time
from pathlib import Path

from testgen.clients.openai_client import OpenAIClient
from testgen.clients.base import LLMError
from testgen.models import LLMResponse

DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-v4-flash-0731:free"


class OpenRouterClient(OpenAIClient):
    """OpenRouter client with automatic key discovery, reasoning suppression, and free model default."""

    def __init__(
        self,
        model: str = DEFAULT_OPENROUTER_MODEL,
        base_url: str = "https://openrouter.ai/api/v1",
        api_key: str | None = None,
        cache_dir: str | Path | None = None,
    ):
        key = (
            api_key
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("TESTGEN_OPENROUTER_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        super().__init__(
            model=model,
            base_url=base_url,
            api_key=key,
            cache_dir=cache_dir,
        )

    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        from openai import APIError, APITimeoutError, RateLimitError

        # Check cache first
        key = self._cache_key(messages, temperature)
        cached = self._cache_get(key)
        if cached is not None:
            return LLMResponse(
                text=cached,
                model=self.model + ":cached",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0.0,
            )

        # Exponential backoff: 3 retries
        last_exc: Exception | None = None
        for attempt in range(3):
            start = time.monotonic()
            try:
                # Disable internal reasoning token consumption on OpenRouter so the model
                # spends its full token budget directly generating clean code.
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra_body={"reasoning": {"max_tokens": 0}},
                )
                break
            except (APITimeoutError, RateLimitError) as e:
                last_exc = e
                time.sleep(2 ** attempt)
            except APIError as e:
                raise LLMError(str(e)) from e
        else:
            raise LLMError(f"API failed after 3 attempts: {last_exc}") from last_exc

        latency_ms = (time.monotonic() - start) * 1000
        msg = resp.choices[0].message
        text = msg.content or ""
        
        # Fallback in case a reasoning model places code inside reasoning
        if not text and hasattr(msg, "reasoning") and msg.reasoning:
            text = msg.reasoning

        usage = getattr(resp, "usage", None)
        self._cache_put(key, text)
        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency_ms,
        )
