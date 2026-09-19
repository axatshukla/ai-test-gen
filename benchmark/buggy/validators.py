"""Validation functions -- BUGGY IMPLEMENTATION."""
from __future__ import annotations
import re


def validate_ipv4(ip: str) -> bool:
    """Validate standard IPv4 address."""
    if not isinstance(ip, str) or not ip:
        return False
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit():
            return False
        # BUG: omitted leading zero check! Accepts '192.168.01.1'
        val = int(p)
        if val < 0 or val > 255:
            return False
    return True


def validate_semver(version: str) -> bool:
    """Validate Semantic Versioning string."""
    if not isinstance(version, str) or not version:
        return False
    parts = version.split(".")
    # BUG: allows 2-component version like '1.0'
    if len(parts) not in (2, 3):
        return False
    for p in parts:
        if not p.isdigit():
            return False
        if len(p) > 1 and p[0] == "0":
            return False
    return True


def validate_password_strength(password: str, min_length: int = 8) -> bool:
    """Validate password against security policy."""
    if min_length < 4:
        raise ValueError("min_length must be at least 4")
    # BUG: off-by-one check requires STRICTLY greater than min_length!
    if not isinstance(password, str) or len(password) <= min_length:
        return False
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    special_chars = set("!@#$%^&*()-_=+[]{}|;:,.<>?")
    has_special = any(c in special_chars for c in password)
    return has_lower and has_upper and has_digit and has_special
