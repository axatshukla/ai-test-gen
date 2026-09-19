"""Versioned prompt templates.
RULE: Never edit a template in place. Bump the version constant and keep the old one.
Every run logs which version produced which output -- this is your NOTES.md evidence.
"""
from __future__ import annotations
from testgen.models import FunctionSpec

# -- Version registry ----------------------------------------------------------
PROMPT_REGISTRY = {}   # version_string -> {"code": fn, "spec": fn, "plan": fn, "repair": fn}

CODE_MODE_VERSION   = "CODE_MODE_V3"
SPEC_MODE_VERSION   = "SPEC_MODE_V3"
TEST_PLAN_VERSION   = "TEST_PLAN_V3"
REPAIR_VERSION      = "REPAIR_V2"

# -- Shared system rules (v3 -- most complete, used in all templates) ----------
_SYSTEM_RULES_V3 = """\
You are a senior SDET writing pytest test suites.

OUTPUT CONTRACT:
- Output ONLY Python code inside a single fenced ```python ... ``` block.
- No prose, explanation, or markdown before or after the code block.

IMPORT RULES:
- Allowed imports: pytest, and `from module_under_test import *`
- Never import os, subprocess, socket, shutil, sys, pathlib, or any stdlib IO module.
- Never use eval(), exec(), open(), or __import__().

NAMING CONVENTION:
- Test functions: test_<function>_<condition>_<expected_outcome>
- Use @pytest.mark.parametrize for families of similar inputs.
- Use pytest.approx for all float comparisons.

COVERAGE REQUIREMENTS -- include at least one test from EACH applicable category:
  1. Happy path (normal, valid input)
  2. Boundary values (0, 1, -1, empty string, empty list, single-element, min/max)
  3. Invalid types and None inputs
  4. Edge cases (unicode, whitespace, large values, duplicates, where applicable)
  5. Error paths -- one pytest.raises test per documented or raised exception

AMBIGUITY RULE (mandatory):
  If the specification does NOT clearly state what should happen for an input,
  do NOT guess. Emit the test but mark it:
      @pytest.mark.xfail(reason="spec ambiguous: <what is unspecified>")
  Never invent an expected value the specification does not state.
"""

# -- Few-shot example (shared) -------------------------------------------------
_FEW_SHOT = '''EXAMPLE INPUT:
def clamp(value: float, low: float, high: float) -> float:
    """Return value restricted to [low, high]. Raises ValueError if low > high."""
    if low > high:
        raise ValueError("low must be <= high")
    return max(low, min(value, high))

EXAMPLE OUTPUT:
```python
import pytest
from module_under_test import *


@pytest.mark.parametrize("value,low,high,expected", [
    (5, 0, 10, 5),       # happy path -- inside range
    (-5, 0, 10, 0),      # below low boundary
    (15, 0, 10, 10),     # above high boundary
    (0, 0, 10, 0),       # exactly at low boundary
    (10, 0, 10, 10),     # exactly at high boundary
    (0, 0, 0, 0),        # degenerate: low == high
])
def test_clamp_various_inputs_returns_clamped(value, low, high, expected):
    assert clamp(value, low, high) == pytest.approx(expected)


def test_clamp_invalid_range_raises_value_error():
    with pytest.raises(ValueError):
        clamp(5, 10, 0)


@pytest.mark.xfail(reason="spec ambiguous: behavior for NaN inputs not specified")
def test_clamp_nan_input():
    clamp(float("nan"), 0, 10)
```
'''

# -- Naive baseline prompt (v1) -- kept for the experiment comparison ----------
_SYSTEM_RULES_V1 = "Write pytest tests for this Python function."


def build_code_mode_prompt_v1(spec: FunctionSpec) -> list[dict]:
    """Naive baseline -- what you get without any prompt engineering."""
    return [
        {"role": "system", "content": _SYSTEM_RULES_V1},
        {"role": "user",   "content": f"Write tests for:\n```python\n{spec.source}\n```"},
    ]


# -- Code mode (v3) ------------------------------------------------------------
def build_code_mode_prompt(spec: FunctionSpec) -> list[dict]:
    """Generate tests from the implementation source (white-box / code mode)."""
    user = f"""{_FEW_SHOT}
Now generate tests for this function:

```python
{spec.source}
```

Documented/raised exceptions: {spec.raises or "none documented"}
Function signature: {spec.signature}
"""
    return [
        {"role": "system", "content": _SYSTEM_RULES_V3},
        {"role": "user",   "content": user},
    ]


# -- Spec mode (v3) ------------------------------------------------------------
def build_spec_mode_prompt(spec: FunctionSpec) -> list[dict]:
    """Generate tests from ONLY the docstring/spec -- no implementation shown.
    This is the contamination-free (black-box) mode.
    """
    spec_text = spec.docstring or f"A function named `{spec.name}` with signature: {spec.signature}"
    user = f"""{_FEW_SHOT}
Generate tests based ONLY on this requirement description.
You are NOT shown the implementation -- do not assume any implementation detail.

Requirement:
\"\"\"{spec_text}\"\"\"

Assume this signature: {spec.signature}
"""
    return [
        {"role": "system", "content": _SYSTEM_RULES_V3},
        {"role": "user",   "content": user},
    ]


# -- Repair prompt (v2) --------------------------------------------------------
def build_repair_prompt(
    previous_code: str,
    failure_summary: str,
    uncovered_lines: list[tuple[int, str]],
) -> list[dict]:
    """Feed failure tracebacks and missing source lines back into the model."""
    uncovered_str = "\n".join(
        f"  line {ln}: {txt}" for ln, txt in uncovered_lines
    ) or "  (none -- only failing tests, no coverage gap)"
    user = f"""Your previous test file was:

```python
{previous_code}
```

Running it produced these problems:
{failure_summary}

These source lines were NOT exercised by any test (add tests to cover them):
{uncovered_str}

RULES:
- Produce a CORRECTED, COMPLETE replacement test file -- not a patch or diff.
- Keep tests that already pass UNCHANGED.
- Add or fix only what is listed above.
- Follow all original rules (import allowlist, naming convention, xfail rule).
- Output ONLY the fenced ```python block.
"""
    return [
        {"role": "system", "content": _SYSTEM_RULES_V3},
        {"role": "user",   "content": user},
    ]


# -- Test plan prompt (v3) -----------------------------------------------------
_TEST_PLAN_SYSTEM_V3 = """\
You are a senior QA engineer writing a structured test plan.

Output ONLY a JSON array -- no prose, no markdown fences.
Each element must have EXACTLY these keys:
  id, category, precondition, steps, expected_result, priority

Constraints:
- category: one of: functional, boundary, negative, security, performance, concurrency
- priority: one of: P0, P1, P2
- Include at least one case from each applicable category.
- id format: TC-001, TC-002, ...
"""


def build_test_plan_prompt(spec_text: str) -> list[dict]:
    return [
        {"role": "system", "content": _TEST_PLAN_SYSTEM_V3},
        {"role": "user",   "content": f'Requirement:\n"""{spec_text}"""'},
    ]
