import pytest
from benchmark.functions.validators import validate_ipv4, validate_semver, validate_password_strength


def test_validate_ipv4():
    assert validate_ipv4("192.168.1.1") is True
    assert validate_ipv4("0.0.0.0") is True
    assert validate_ipv4("255.255.255.255") is True
    assert validate_ipv4("192.168.01.1") is False  # leading zero invalid
    assert validate_ipv4("256.1.1.1") is False
    assert validate_ipv4("192.168.1") is False
    assert validate_ipv4("abc.def.ghi.jkl") is False


def test_validate_semver():
    assert validate_semver("1.0.0") is True
    assert validate_semver("0.1.23") is True
    assert validate_semver("1.0") is False  # requires 3 segments
    assert validate_semver("01.0.0") is False  # no leading zeros
    assert validate_semver("1.0.0-beta") is False


def test_validate_password_strength():
    assert validate_password_strength("Passw0rd!") is True
    assert validate_password_strength("short1!", min_length=8) is False
    assert validate_password_strength("exact8!P", min_length=8) is True
    assert validate_password_strength("nocapital1!") is False
    assert validate_password_strength("NOLOWER1!") is False
    assert validate_password_strength("NoDigits!!") is False
    assert validate_password_strength("NoSpecial123") is False
    with pytest.raises(ValueError):
        validate_password_strength("test", min_length=2)
