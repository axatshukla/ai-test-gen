"""Validation functions for network, version, and security formats."""
from __future__ import annotations
import re


def validate_ipv4(ip: str) -> bool:
    """Validate standard IPv4 address in dotted-decimal notation (e.g. 192.168.1.1).

    Must have exactly 4 octets, each 0-255, with no leading zeros (e.g. '01' is invalid).
    Returns False for non-string, empty string, or invalid format.
    """
    if not isinstance(ip, str) or not ip:
        return False
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit():
            return False
        if len(p) > 1 and p[0] == "0":
            return False
        val = int(p)
        if val < 0 or val > 255:
            return False
    return True


def validate_semver(version: str) -> bool:
    """Validate Semantic Versioning string in format MAJOR.MINOR.PATCH (e.g. 1.2.3).

    Each segment must be a non-negative integer without leading zeros.
    Returns False for invalid formats or non-string inputs.
    """
    if not isinstance(version, str) or not version:
        return False
    parts = version.split(".")
    if len(parts) != 3:
        return False
    for p in parts:
        if not p.isdigit():
            return False
        if len(p) > 1 and p[0] == "0":
            return False
    return True


def validate_password_strength(password: str, min_length: int = 8) -> bool:
    """Validate password against security policy.

    Requires:
    - Length >= min_length
    - At least one lowercase letter
    - At least one uppercase letter
    - At least one digit
    - At least one special symbol (!@#$%^&*()-_=+[]{}|;:,.<>?)
    Raises ValueError if min_length < 4.
    """
    if min_length < 4:
        raise ValueError("min_length must be at least 4")
    if not isinstance(password, str) or len(password) < min_length:
        return False
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    special_chars = set("!@#$%^&*()-_=+[]{}|;:,.<>?")
    has_special = any(c in special_chars for c in password)
    return has_lower and has_upper and has_digit and has_special
