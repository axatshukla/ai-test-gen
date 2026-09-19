"""Full end-to-end pipeline test using FakeLLMClient -- zero API calls, safe for CI."""
import pytest
from testgen.clients.fake_client import FakeLLMClient
from testgen.extractor import extract_functions
from testgen.prompts import build_code_mode_prompt
from testgen.repair import generate_with_repair

MODULE_SOURCE = """\
def add(a: int, b: int) -> int:
    \"\"\"Add two numbers. Raises ValueError if either is negative.\"\"\"
    if a < 0 or b < 0:
        raise ValueError("no negatives")
    return a + b
"""

# Canned tests that pass against the add function above
CANNED_TESTS = """\
```python
import pytest
from module_under_test import *


@pytest.mark.parametrize("a,b,expected", [
    (2, 3, 5),
    (0, 0, 0),
    (100, 200, 300),
])
def test_add_happy_path(a, b, expected):
    assert add(a, b) == expected


def test_add_negative_raises():
    with pytest.raises(ValueError):
        add(-1, 2)
```
"""


def test_pipeline_end_to_end_with_fake_client(tmp_path):
    """The full pipeline should succeed on a simple function without any real LLM call."""
    mod_file = tmp_path / "mod.py"
    mod_file.write_text(MODULE_SOURCE)

    specs = extract_functions(str(mod_file))
    assert specs, "Extractor should find the add function"

    spec = specs[0]
    messages = build_code_mode_prompt(spec)

    client = FakeLLMClient(canned=CANNED_TESTS)
    final_code, final_result, attempts = generate_with_repair(
        client, messages, MODULE_SOURCE,
        function_name="add", mode="code",
        model="fake", prompt_version="CODE_MODE_V3",
        target_coverage=0.0,  # set to 0 so it doesn't need real coverage
        max_iters=1,
    )

    assert final_result is not None, "Pipeline should produce a result"
    assert final_result.failed == 0, f"Tests should not fail: {final_result.failure_details}"
    assert len(attempts) == 1


def test_pipeline_sanitizer_rejects_bad_code(tmp_path):
    """If the fake client returns unsafe code, sanitizer should block it."""
    bad_canned = "```python\nimport os\ndef test_x():\n    os.system('ls')\n```"
    mod_file = tmp_path / "mod.py"
    mod_file.write_text("def add(a, b):\n    return a + b\n")

    specs = extract_functions(str(mod_file))
    messages = build_code_mode_prompt(specs[0])
    client = FakeLLMClient(canned=bad_canned)

    final_code, final_result, attempts = generate_with_repair(
        client, messages, "def add(a, b):\n    return a + b\n",
        function_name="add", mode="code",
        model="fake", prompt_version="test",
        max_iters=1,
    )

    # Every attempt failed sanitization, so result should be None
    assert final_result is None
    assert all(not a.sanitize_ok for a in attempts)
