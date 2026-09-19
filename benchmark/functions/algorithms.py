"""Core algorithms and rate-limiting / retry helpers."""
from __future__ import annotations


def binary_search(arr: list[int], target: int) -> int:
    """Perform binary search on a sorted list of integers.

    Returns the 0-based index of target if found, or -1 if not present.
    Raises TypeError if arr elements or target are not comparable integers.
    """
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
            high = mid - 1
    return -1


def token_bucket(
    capacity: int,
    fill_rate: float,
    current_tokens: float,
    time_elapsed: float,
    requested: int = 1,
) -> tuple[bool, float]:
    """Evaluate rate-limiting token bucket.

    Tokens replenish at fill_rate tokens/second over time_elapsed, capped at capacity.
    If requested tokens are available, deduct them and return (True, remaining_tokens).
    Otherwise, return (False, current_replenished_tokens).
    Raises ValueError if capacity <= 0 or fill_rate < 0 or time_elapsed < 0 or requested <= 0.
    """
    if capacity <= 0:
        raise ValueError("capacity must be positive")
    if fill_rate < 0 or time_elapsed < 0:
        raise ValueError("fill_rate and time_elapsed must be non-negative")
    if requested <= 0:
        raise ValueError("requested must be positive")
    replenished = min(float(capacity), current_tokens + (fill_rate * time_elapsed))
    if replenished >= requested:
        return (True, replenished - requested)
    return (False, replenished)


def retry_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
) -> float:
    """Calculate exponential backoff delay for retry attempts.

    delay = min(max_delay, base_delay * (backoff_factor ** attempt)).
    Attempt is 0-indexed (attempt 0 gives base_delay).
    Raises ValueError if attempt < 0, base_delay <= 0, or max_delay < base_delay.
    """
    if attempt < 0:
        raise ValueError("attempt must be non-negative")
    if base_delay <= 0:
        raise ValueError("base_delay must be positive")
    if max_delay < base_delay:
        raise ValueError("max_delay must be >= base_delay")
    delay = base_delay * (backoff_factor ** attempt)
    return min(max_delay, delay)
