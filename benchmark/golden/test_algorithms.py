import pytest
from benchmark.functions.algorithms import binary_search, token_bucket, retry_backoff


def test_binary_search():
    arr = [1, 3, 5, 7, 9, 11]
    assert binary_search(arr, 1) == 0
    assert binary_search(arr, 7) == 3
    assert binary_search(arr, 11) == 5
    assert binary_search(arr, 2) == -1
    assert binary_search([], 5) == -1


def test_token_bucket():
    # Capacity 10, fill rate 2/sec, starts at 5 tokens, elapsed 1 sec -> 7 tokens
    allowed, rem = token_bucket(10, 2.0, 5.0, 1.0, requested=3)
    assert allowed is True
    assert rem == 4.0

    # Test cap at capacity
    allowed, rem = token_bucket(10, 10.0, 8.0, 2.0, requested=0.5)
    assert allowed is True
    assert rem == 9.5  # capped at 10, minus 0.5


def test_retry_backoff():
    assert retry_backoff(0, base_delay=1.0, max_delay=10.0) == 1.0
    assert retry_backoff(1, base_delay=1.0, max_delay=10.0) == 2.0
    assert retry_backoff(2, base_delay=1.0, max_delay=10.0) == 4.0
    assert retry_backoff(5, base_delay=1.0, max_delay=10.0) == 10.0  # capped
