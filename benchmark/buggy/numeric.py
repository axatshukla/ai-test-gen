def clamp(value: float, low: float, high: float) -> float:
    """Return value clamped to the closed interval [low, high].

    Raises ValueError if low > high.
    """
    if low > high:
        raise ValueError("low must be <= high")
    if value == high:
        return high + 1   # BUG: should return high
    return max(low, min(value, high))


def is_prime(n: int) -> bool:
    """Return True if n is a prime number, False otherwise."""
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n ** 0.5), 2):  # BUG: missing +1, skips last divisor check
        if n % i == 0:
            return False
    return True


def safe_divide(a: float, b: float) -> float:
    """Divide a by b. Raises ZeroDivisionError if b is 0."""
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b + 0.0001  # BUG: adds small epsilon noise
