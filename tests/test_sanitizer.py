"""Unit tests for the sanitizer -- must cover the full adversarial corpus."""
import pytest
from testgen.sanitizer import sanitize, strip_fences

# -- strip_fences --------------------------------------------------------------

def test_strip_fences_python_fenced():
    raw = "```python\ndef test_x():\n    assert True\n```"
    assert "def test_x" in strip_fences(raw)
    assert "```" not in strip_fences(raw)

def test_strip_fences_plain_fenced():
    raw = "```\ndef test_x():\n    assert True\n```"
    assert "def test_x" in strip_fences(raw)

def test_strip_fences_unfenced():
    raw = "def test_x():\n    assert True"
    assert strip_fences(raw) == raw

def test_strip_fences_prose_before_code():
    # If model outputs prose before fenced block, strip_fences only handles fences
    raw = "Here is your code:\n```python\ndef test_x():\n    pass\n```"
    # strip_fences removes the ``` markers; prose is still there
    result = strip_fences(raw)
    assert "def test_x" in result

# -- sanitize gates ------------------------------------------------------------

VALID_CODE = "```python\nimport pytest\nfrom module_under_test import *\n\ndef test_x():\n    assert True\n```"

def test_sanitize_valid_code_passes():
    r = sanitize(VALID_CODE)
    assert r.ok is True
    assert "def test_x" in r.code

def test_sanitize_empty_output_fails():
    r = sanitize("   ")
    assert r.ok is False
    assert "empty" in r.error

def test_sanitize_no_test_functions_fails():
    r = sanitize("def helper():\n    pass")
    assert r.ok is False
    assert "test_" in r.error

def test_sanitize_syntax_error_fails():
    r = sanitize("def test_x(:\n    pass")
    assert r.ok is False
    assert "syntax" in r.error

def test_sanitize_os_import_rejected():
    r = sanitize("import os\ndef test_x():\n    pass")
    assert r.ok is False
    assert "os" in r.error

def test_sanitize_subprocess_rejected():
    r = sanitize("import subprocess\ndef test_x():\n    pass")
    assert r.ok is False

def test_sanitize_from_os_rejected():
    r = sanitize("from os import path\ndef test_x():\n    pass")
    assert r.ok is False

def test_sanitize_dunder_import_rejected():
    r = sanitize("def test_x():\n    __import__('os')")
    assert r.ok is False
    assert "__import__" in r.error

def test_sanitize_eval_rejected():
    r = sanitize("def test_x():\n    eval('1+1')")
    assert r.ok is False
    assert "eval" in r.error

def test_sanitize_exec_rejected():
    r = sanitize("def test_x():\n    exec('pass')")
    assert r.ok is False

def test_sanitize_open_rejected():
    r = sanitize("def test_x():\n    open('/etc/passwd')")
    assert r.ok is False

def test_sanitize_allowed_stdlib_passes():
    code = "import pytest\nimport math\nfrom module_under_test import *\n\ndef test_x():\n    assert math.sqrt(4) == pytest.approx(2.0)\n"
    r = sanitize(code)
    assert r.ok is True
