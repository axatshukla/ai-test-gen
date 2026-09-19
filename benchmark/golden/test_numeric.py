import pytest
from benchmark.functions.numeric import clamp, is_prime, safe_divide


def test_clamp_basic():
    assert clamp(5, 0, 10) == 5
    assert clamp(-5, 0, 10) == 0
    assert clamp(15, 0, 10) == 10
    assert clamp(10, 0, 10) == 10


def test_clamp_invalid_bounds():
    with pytest.raises(ValueError):
        clamp(5, 10, 0)


def test_is_prime():
    assert not is_prime(0)
    assert not is_prime(1)
    assert is_prime(2)
    assert is_prime(3)
    assert not is_prime(4)
    assert not is_prime(9)
    assert is_prime(13)
    assert not is_prime(25)


def test_safe_divide():
    assert safe_divide(10, 2) == 5.0
    with pytest.raises(ZeroDivisionError):
        safe_divide(5, 0)
