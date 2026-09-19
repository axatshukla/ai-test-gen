"""Collection manipulation utilities -- BUGGY IMPLEMENTATION."""
from __future__ import annotations
from typing import Any


def flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """Recursively flatten a nested dictionary with delimited keys."""
    if not isinstance(d, dict):
        raise TypeError("Input must be a dictionary")
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            # BUG: accidentally stringifies all values
            items.append((new_key, str(v)))
    return dict(items)


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """Split a list into consecutive sublists of length chunk_size."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if not lst:
        return []
    # BUG: drops the final partial chunk if length not cleanly divisible!
    n_full = (len(lst) // chunk_size) * chunk_size
    return [lst[i : i + chunk_size] for i in range(0, n_full, chunk_size)]


def deep_merge(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge dict2 into dict1."""
    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        raise TypeError("Both arguments must be dictionaries")
    # BUG: mutates dict1 directly in place!
    for k, v in dict2.items():
        if k in dict1 and isinstance(dict1[k], dict) and isinstance(v, dict):
            dict1[k] = deep_merge(dict1[k], v)
        else:
            dict1[k] = v
    return dict1
