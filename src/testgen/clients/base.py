"""LLM client abstract base class and shared data types."""
from __future__ import annotations
from abc import ABC, abstractmethod
from testgen.models import LLMResponse


class LLMError(Exception):
    """Raised for any backend failure: timeout, rate limit, malformed response."""


class LLMClient(ABC):
    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse: ...
