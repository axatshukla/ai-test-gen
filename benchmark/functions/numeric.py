def clamp(value: float, low: float, high: float) -> float:
    """Return value clamped to the closed interval [low, high].

    Raises ValueError if low > high.
    """
    if low > high:
        raise ValueError("low must be <= high")
    return max(low, min(value, high))


def is_prime(n: int) -> bool:
    """Return True if n is a prime number, False otherwise.

    1 and numbers < 1 are not prime. 2 is the only even prime.
    """
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n ** 0.5) + 1, 2):
        if n % i == 0:
            return False
    return True


def safe_divide(a: float, b: float) -> float:
    """Divide a by b.

    Raises ZeroDivisionError if b is 0.
    """
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b
