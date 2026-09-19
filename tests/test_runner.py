"""Unit tests for the sandboxed pytest runner."""
import pytest
from testgen.runner import run_tests

MODULE_ADD = "def add(a, b):\n    return a + b\n"
TEST_ADD_PASS = "from module_under_test import *\ndef test_add():\n    assert add(2, 3) == 5\n"
TEST_ADD_FAIL = "from module_under_test import *\ndef test_add():\n    assert add(2, 3) == 99\n"

def test_runner_passing_tests():
    result = run_tests(MODULE_ADD, TEST_ADD_PASS)
    assert result.passed == 1
    assert result.failed == 0
    assert result.raw_ok is True

def test_runner_failing_tests():
    result = run_tests(MODULE_ADD, TEST_ADD_FAIL)
    assert result.failed == 1
    assert len(result.failure_details) == 1

def test_runner_returns_coverage():
    result = run_tests(MODULE_ADD, TEST_ADD_PASS)
    assert result.branch_coverage >= 0.0

def test_runner_timeout():
    inf_module = "def spin():\n    while True:\n        pass\n"
    inf_test = "from module_under_test import *\ndef test_spin():\n    spin()\n"
    result = run_tests(inf_module, inf_test, timeout=3)
    assert result.error_message == "execution_timeout"
    assert result.raw_ok is False
