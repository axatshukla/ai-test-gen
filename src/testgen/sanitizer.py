"""5-gate security sanitizer for all LLM output.
Every generated code fragment passes through here before touching disk or subprocess.
"""
from __future__ import annotations
import ast
import re
from testgen.models import SanitizeResult

# Modules that generated tests are allowed to import
ALLOWED_MODULES = frozenset({
    "pytest",
    "module_under_test",
    "math",
    "typing",
    "re",
    "string",
    "decimal",
    "fractions",
    "collections",
    "itertools",
    "functools",
    "dataclasses",
    "enum",
    "datetime",
    "copy",
    "json",
})

# Function calls that are never allowed in generated code
DISALLOWED_CALLS = frozenset({"eval", "exec", "__import__", "open", "compile"})

# Modules that are never allowed, even if they look stdlib-safe
HARD_BLOCKED_MODULES = frozenset({
    "os", "sys", "subprocess", "socket", "shutil", "pathlib",
    "importlib", "ctypes", "multiprocessing", "threading", "asyncio",
    "ftplib", "http", "urllib", "requests", "httpx",
})


class SanitizationError(Exception):
    pass


def strip_fences(raw: str) -> str:
    """Remove markdown code fences (```python or ```) from model output."""
    text = raw.strip()
    text = re.sub(r"^```(?:python)?\s*\n", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def sanitize(raw: str, extra_allowed: set[str] | None = None) -> SanitizeResult:
    """Run all 5 gates and return SanitizeResult(ok=True/False, code, error)."""
    allowed = ALLOWED_MODULES | (extra_allowed or set())

    # Gate 1: strip fences
    code = strip_fences(raw)

    if not code.strip():
        return SanitizeResult(ok=False, error="empty output after fence stripping")

    # Gate 2: must contain at least one test function
    if "def test_" not in code:
        return SanitizeResult(ok=False, error="no test_ functions found in output")

    # Gate 3: syntax check
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return SanitizeResult(ok=False, error=f"syntax error: {e}")

    # Gate 4: import allowlist
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in HARD_BLOCKED_MODULES or root not in allowed:
                    return SanitizeResult(ok=False, error=f"disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in HARD_BLOCKED_MODULES or root not in allowed:
                return SanitizeResult(ok=False, error=f"disallowed import from: {node.module}")

    # Gate 5: banned function calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            fname = (func.id if isinstance(func, ast.Name)
                     else getattr(func, "attr", None))
            if fname in DISALLOWED_CALLS:
                return SanitizeResult(ok=False, error=f"disallowed call: {fname}()")

    return SanitizeResult(ok=True, code=code)
