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

_SLUGIFY_CANNED = """```python
import pytest
from module_under_test import *


@pytest.mark.parametrize("text,expected", [
    ("Hello World", "hello-world"),
    ("hello---world", "hello-world"),
    ("  abc  ", "abc"),
    ("123 test", "123-test"),
    ("foo @ bar", "foo-bar"),
])
def test_slugify_happy_path(text, expected):
    assert slugify(text) == expected


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        slugify("   ")
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
        # If the user asked specifically for slugify in smoke/CI tests, provide matching suite
        user_prompt = " ".join(m.get("content", "") for m in messages if isinstance(m, dict))
        if "slugify" in user_prompt:
            return LLMResponse(text=_SLUGIFY_CANNED, model="fake-client", prompt_tokens=100, completion_tokens=200, latency_ms=1.0)
        return LLMResponse(text=self._response, model="fake-client", prompt_tokens=100, completion_tokens=200, latency_ms=1.0)
