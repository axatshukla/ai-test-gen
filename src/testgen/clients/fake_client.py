"""Deterministic fake LLM client. No API calls."""
from __future__ import annotations
from pathlib import Path
from testgen.clients.base import LLMClient
from testgen.models import LLMResponse

_DEFAULT_CANNED = """```python
import pytest
from module_under_test import *


@pytest.mark.parametrize("a,b,expected", [(2, 3, 5), (0, 0, 0), (-1, 1, 0)])
def test_add_happy_path(a, b, expected):
    assert add(a, b) == expected


def test_add_negative_raises():
    with pytest.raises(ValueError):
        add(-1, 2)
```"""


class FakeLLMClient(LLMClient):
    def __init__(self, fixture_path=None, canned: str | None = None):
        if fixture_path:
            self._response = Path(fixture_path).read_text(encoding="utf-8")
        elif canned:
            self._response = canned
        else:
            self._response = _DEFAULT_CANNED

    def generate(self, messages, temperature=0.2, max_tokens=2048) -> LLMResponse:
        return LLMResponse(text=self._response, model="fake-client", prompt_tokens=100, completion_tokens=200, latency_ms=1.0)
