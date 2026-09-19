import pytest
from benchmark.functions.collections_ops import flatten_dict, chunk_list, deep_merge


def test_flatten_dict():
    d = {"a": 1, "b": {"c": 2, "d": {"e": 3}}}
    assert flatten_dict(d) == {"a": 1, "b.c": 2, "b.d.e": 3}
    assert flatten_dict({}) == {}
    with pytest.raises(TypeError):
        flatten_dict([1, 2, 3])


def test_chunk_list():
    assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert chunk_list([1, 2, 3], 3) == [[1, 2, 3]]
    assert chunk_list([], 2) == []
    with pytest.raises(ValueError):
        chunk_list([1, 2], 0)


def test_deep_merge():
    d1 = {"a": 1, "b": {"x": 10}}
    d2 = {"b": {"y": 20}, "c": 30}
    merged = deep_merge(d1, d2)
    assert merged == {"a": 1, "b": {"x": 10, "y": 20}, "c": 30}
    # Ensure d1 is not mutated
    assert "y" not in d1["b"]
