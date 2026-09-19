"""Collection manipulation utilities."""
from __future__ import annotations
from typing import Any


def flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """Recursively flatten a nested dictionary with delimited keys.

    Raises TypeError if d is not a dict.
    Returns an empty dict if d is empty.
    """
    if not isinstance(d, dict):
        raise TypeError("Input must be a dictionary")
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """Split a list into consecutive sublists of length chunk_size.

    The last chunk may contain fewer elements if len(lst) is not divisible by chunk_size.
    Raises ValueError if chunk_size <= 0.
    Returns an empty list if lst is empty.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if not lst:
        return []
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def deep_merge(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge dict2 into dict1, returning a new dictionary without mutating inputs.

    For duplicate keys with dict values, recurse. Otherwise dict2 value overwrites dict1 value.
    Raises TypeError if either argument is not a dict.
    """
    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        raise TypeError("Both arguments must be dictionaries")
    result = dict(dict1)
    for k, v in dict2.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result
