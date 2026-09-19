"""Core algorithms -- BUGGY IMPLEMENTATION."""
from __future__ import annotations


def binary_search(arr: list[int], target: int) -> int:
    """Perform binary search on a sorted list."""
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        mid_val = arr[mid]
        if mid_val == target:
            return mid
        elif mid_val < target:
            low = mid + 1
        else:
            # BUG: sets high = mid instead of mid - 1, causing potential infinite loop on boundary
            high = mid if high != mid else mid - 1
    return -1


def token_bucket(
    capacity: int,
    fill_rate: float,
    current_tokens: float,
    time_elapsed: float,
    requested: int = 1,
) -> tuple[bool, float]:
    """Evaluate rate-limiting token bucket."""
    if capacity <= 0:
        raise ValueError("capacity must be positive")
    if fill_rate < 0 or time_elapsed < 0:
        raise ValueError("fill_rate and time_elapsed must be non-negative")
    if requested <= 0:
        raise ValueError("requested must be positive")
    # BUG: fails to cap replenished tokens at capacity!
    replenished = current_tokens + (fill_rate * time_elapsed)
    if replenished >= requested:
        return (True, replenished - requested)
    return (False, replenished)


def retry_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
) -> float:
    """Calculate exponential backoff delay."""
    if attempt < 0:
        raise ValueError("attempt must be non-negative")
    if base_delay <= 0:
        raise ValueError("base_delay must be positive")
    if max_delay < base_delay:
        raise ValueError("max_delay must be >= base_delay")
    # BUG: never clamps to max_delay! Delay grows unboundedly
    return base_delay * (backoff_factor ** attempt)
