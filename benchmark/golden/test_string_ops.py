import pytest
from benchmark.functions.string_ops import slugify, truncate, count_words


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"
    assert slugify("  Trailing & Leading  ") == "trailing-leading"
    assert slugify("Special @#$ Characters!") == "special-characters"


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        slugify("   ")


def test_truncate_basic():
    assert truncate("hello world", 8) == "hello..."
    assert truncate("short", 10) == "short"
    assert truncate("exact", 5) == "exact"


def test_truncate_invalid_max_len():
    with pytest.raises(ValueError):
        truncate("test", 2, "...")


def test_count_words_basic():
    assert count_words("hello world from pytest") == 4
    assert count_words("") == 0
    assert count_words("   \t\n  ") == 0
