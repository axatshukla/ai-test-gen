"""Unit tests for the AST extractor."""
import pytest
from testgen.extractor import extract_functions

FIXTURE_SIMPLE = (
    "def add(a: int, b: int) -> int:\n"
    "    'Add two numbers. Raises ValueError if either is negative.'\n"
    "    if a < 0 or b < 0:\n"
    "        raise ValueError('no negatives')\n"
    "    return a + b\n"
)

FIXTURE_CLASS = (
    "class Calculator:\n"
    "    def multiply(self, x: float, y: float) -> float:\n"
    "        'Multiply two numbers.'\n"
    "        return x * y\n"
    "\n"
    "    def _private(self):\n"
    "        pass\n"
)

FIXTURE_ASYNC = (
    "async def fetch(url: str) -> str:\n"
    "    'Fetch a URL.'\n"
    "    pass\n"
)


def test_extract_basic(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text(FIXTURE_SIMPLE)
    specs = extract_functions(str(f))
    assert len(specs) == 1
    s = specs[0]
    assert s.name == "add"
    assert s.returns == "int"
    assert "ValueError" in s.raises
    assert ("a", "int") in s.params
    assert s.is_async is False


def test_extract_class_method(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text(FIXTURE_CLASS)
    specs = extract_functions(str(f))
    names = [s.name for s in specs]
    assert "multiply" in names
    assert "_private" not in names
    mul = next(s for s in specs if s.name == "multiply")
    assert mul.is_method is True
    assert mul.qualname == "Calculator.multiply"


def test_extract_async(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text(FIXTURE_ASYNC)
    specs = extract_functions(str(f))
    assert specs[0].is_async is True


def test_extract_filter_by_name(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text(FIXTURE_SIMPLE)
    specs = extract_functions(str(f), function_name="add")
    assert len(specs) == 1
    assert specs[0].name == "add"


def test_extract_filter_no_match(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text(FIXTURE_SIMPLE)
    specs = extract_functions(str(f), function_name="nonexistent")
    assert specs == []
