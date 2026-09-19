# Implementation Guide (Step by Step, With Working Code)
## AI-Powered Test Case Generator

**Companions:** `01_PRD.md`, `02_TRD.md`, `03_API_AND_SCHEMA_SPEC.md`

This version replaces the earlier high-level guide with actual, runnable code for every file. Follow the phases in order — each phase ends with a **Verify** step you run in your terminal before moving on. If a Verify step doesn't pass, fix it before starting the next phase; the phases build directly on each other, so a broken Phase 1 means a broken Phase 4.

Total estimated time: ~18–19 hours across 5 phases.

---

## Phase 0 — Project Setup (30 min)

**1. Scaffold the repo:**
```bash
mkdir ai-test-generator && cd ai-test-generator
git init
mkdir -p src/ai_test_gen/clients benchmark/functions benchmark/buggy benchmark/golden results tests .github/workflows
touch src/ai_test_gen/__init__.py src/ai_test_gen/clients/__init__.py
```

**2. File: `pyproject.toml`**
```toml
[project]
name = "ai-test-generator"
version = "0.1.0"
description = "AI-powered test case generator with execution, repair, and mutation-based evaluation"
requires-python = ">=3.11"
dependencies = [
    "openai>=1.0.0",
    "pytest>=8.0.0",
    "pytest-json-report>=1.5.0",
    "coverage>=7.0.0",
]

[project.optional-dependencies]
dev = ["matplotlib>=3.8.0"]
hf = ["huggingface_hub>=0.20.0"]

[project.scripts]
ai-test-gen = "ai_test_gen.cli:main"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

**3. Install:**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export OPENAI_API_KEY="sk-..."       # or use a .env file + python-dotenv if you prefer
```

**4. First commit:**
```bash
git add -A && git commit -m "project scaffold"
```

**Verify:** `python -c "import ai_test_gen"` runs with no error.

---

## Phase 1 — Extraction, Prompting, Sanitization (v1 building blocks, ~4h)

These three modules have no side effects (no network, no subprocess) so you can test them fully in isolation before touching the LLM.

### File: `src/ai_test_gen/extractor.py`
```python
"""Static extraction of function specs from a Python source file via ast.
Never imports or executes the target file -- static analysis only."""
from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class FunctionSpec:
    name: str
    args: list[tuple[str, str | None]]
    returns: str | None
    docstring: str | None
    source: str
    is_async: bool
    raises: list[str]
    module_path: str
    qualname: str = ""

    def __post_init__(self):
        if not self.qualname:
            self.qualname = self.name


def _extract_raises(node: ast.AST) -> list[str]:
    raised = []
    for n in ast.walk(node):
        if isinstance(n, ast.Raise) and n.exc is not None:
            target = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
            try:
                raised.append(ast.unparse(target))
            except Exception:
                pass
    seen, out = set(), []
    for r in raised:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def extract_functions(path: str, function_name: str | None = None) -> list[FunctionSpec]:
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src, filename=path)
    specs: list[FunctionSpec] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.class_stack: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef):
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

        def _handle_func(self, node):
            args = []
            for a in node.args.args:
                if a.arg == "self":
                    continue
                ann = ast.unparse(a.annotation) if a.annotation else None
                args.append((a.arg, ann))
            specs.append(FunctionSpec(
                name=node.name,
                args=args,
                returns=ast.unparse(node.returns) if node.returns else None,
                docstring=ast.get_docstring(node),
                source=ast.unparse(node),
                is_async=isinstance(node, ast.AsyncFunctionDef),
                raises=_extract_raises(node),
                module_path=path,
                qualname=".".join(self.class_stack + [node.name]),
            ))

        def visit_FunctionDef(self, node):
            self._handle_func(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node):
            self._handle_func(node)
            self.generic_visit(node)

    Visitor().visit(tree)
    if function_name:
        specs = [s for s in specs if function_name in (s.name, s.qualname)]
    return specs
```

### File: `benchmark/functions/string_ops.py` (your first fixture)
```python
def slugify(text: str) -> str:
    """Convert text to a lowercase, hyphen-separated slug.

    Raises ValueError if the input is empty after stripping whitespace.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        raise ValueError("cannot slugify empty text")
    result = []
    prev_hyphen = False
    for ch in cleaned:
        if ch.isalnum():
            result.append(ch)
            prev_hyphen = False
        elif not prev_hyphen:
            result.append("-")
            prev_hyphen = True
    return "".join(result).strip("-")
```

**Verify:**
```bash
python -c "
from ai_test_gen.extractor import extract_functions
specs = extract_functions('benchmark/functions/string_ops.py')
print(specs[0].name, specs[0].raises, specs[0].docstring)
"
```
Expect: `slugify ['ValueError'] Convert text to a lowercase, hyphen-separated slug. ...`

### File: `src/ai_test_gen/prompts.py`
```python
"""Versioned prompt templates. Bump the version constant, never edit a
template's meaning in place, so runs stay traceable to the exact prompt
that produced them."""
from __future__ import annotations
from ai_test_gen.extractor import FunctionSpec

CODE_MODE_VERSION = "CODE_MODE_V1"
SPEC_MODE_VERSION = "SPEC_MODE_V1"
TEST_PLAN_VERSION = "TEST_PLAN_V1"

_SYSTEM_RULES = """You are a senior SDET writing pytest tests.

RULES:
- Output ONLY Python code in a single fenced ```python block. No prose before or after.
- Import only: pytest, and `from module_under_test import *` for the function(s) under test.
- Name tests: test_<function>_<condition>_<expected_outcome>
- Use @pytest.mark.parametrize for families of similar inputs.
- Use pytest.approx for float comparisons.
- For each exception documented or raised in the source, write a pytest.raises test.

COVERAGE REQUIREMENTS -- include at least one case from each applicable category:
  1. Happy path
  2. Boundary values (0, 1, -1, empty, single-element, max/min where relevant)
  3. Invalid types and None
  4. Edge cases (unicode, large input, duplicates, etc. where relevant)
  5. Error paths (one test per raised/documented exception)

AMBIGUITY RULE: If expected behavior for a case is not clearly specified, do NOT guess.
Emit that test marked @pytest.mark.xfail(reason="spec ambiguous: <why>") with only a call
to the function -- no assertion that encodes a guess.
"""

_FEW_SHOT = '''EXAMPLE

def clamp(value: float, low: float, high: float) -> float:
    """Return value restricted to [low, high]. Raises ValueError if low > high."""
    if low > high:
        raise ValueError("low must be <= high")
    return max(low, min(value, high))

Ideal tests:
```python
import pytest
from module_under_test import *


@pytest.mark.parametrize("value,low,high,expected", [
    (5, 0, 10, 5),
    (-5, 0, 10, 0),
    (15, 0, 10, 10),
    (0, 0, 10, 0),
    (10, 0, 10, 10),
])
def test_clamp_various_ranges_returns_clamped_value(value, low, high, expected):
    assert clamp(value, low, high) == pytest.approx(expected)


def test_clamp_low_greater_than_high_raises_value_error():
    with pytest.raises(ValueError):
        clamp(5, 10, 0)
```
'''


def build_code_mode_prompt(spec: FunctionSpec) -> list[dict]:
    user_content = f"""{_FEW_SHOT}

Now generate tests for this function:

```python
{spec.source}
```

Documented/raised exceptions: {spec.raises or "none"}
"""
    return [{"role": "system", "content": _SYSTEM_RULES},
            {"role": "user", "content": user_content}]


def build_spec_mode_prompt(spec_text: str, function_signature_hint: str) -> list[dict]:
    user_content = f"""{_FEW_SHOT}

Generate tests based ONLY on this requirement (you are NOT shown the implementation):

Requirement:
\"\"\"{spec_text}\"\"\"

Assume this signature: {function_signature_hint}
"""
    return [{"role": "system", "content": _SYSTEM_RULES},
            {"role": "user", "content": user_content}]


def build_repair_prompt(previous_code: str, failure_summary: str,
                         uncovered_lines: list[tuple[int, str]]) -> list[dict]:
    uncovered_str = "\n".join(f"  line {ln}: {txt}" for ln, txt in uncovered_lines) or "  (none)"
    user_content = f"""Your previous test file was:

```python
{previous_code}
```

Running it produced these problems:
{failure_summary}

These source lines were NOT exercised by any test:
{uncovered_str}

Produce a CORRECTED, COMPLETE replacement test file (not a diff). Follow all original rules.
Output ONLY the fenced ```python block."""
    return [{"role": "system", "content": _SYSTEM_RULES},
            {"role": "user", "content": user_content}]


_TEST_PLAN_SYSTEM = """You are a senior QA engineer writing a structured test plan.
Output ONLY a JSON array (no prose, no markdown fences) of objects with EXACTLY these keys:
id, category, precondition, steps, expected_result, priority
- category: one of functional, boundary, negative, security, performance, concurrency
- priority: one of P0, P1, P2
"""


def build_test_plan_prompt(spec_text: str) -> list[dict]:
    return [{"role": "system", "content": _TEST_PLAN_SYSTEM},
            {"role": "user", "content": f'Requirement:\n"""{spec_text}"""'}]
```

### File: `src/ai_test_gen/sanitizer.py`
```python
from __future__ import annotations
import ast
import re

ALLOWED_MODULES_BASE = {"pytest", "math", "typing", "re", "module_under_test"}
DISALLOWED_CALLS = {"eval", "exec", "__import__"}


class SanitizationError(Exception):
    pass


def strip_fences(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^```(?:python)?\n", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def sanitize(raw: str, extra_allowed_modules: set[str] | None = None) -> str:
    allowed = ALLOWED_MODULES_BASE | (extra_allowed_modules or set())
    code = strip_fences(raw)
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SanitizationError(f"syntax error: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in allowed:
                    raise SanitizationError(f"disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in allowed:
                raise SanitizationError(f"disallowed import: {root}")
        elif isinstance(node, ast.Call):
            func = node.func
            fname = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if fname in DISALLOWED_CALLS:
                raise SanitizationError(f"disallowed call: {fname}")
    return code
```

**Verify:**
```bash
python -c "
from ai_test_gen.sanitizer import sanitize, SanitizationError
print(sanitize('\`\`\`python\ndef test_x():\n    assert True\n\`\`\`'))
try:
    sanitize('import os\ndef test_x(): pass')
    print('FAIL: should have rejected os import')
except SanitizationError as e:
    print('OK, rejected:', e)
"
```

### File: `src/ai_test_gen/clients/base.py`
```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMError(Exception):
    """Raised for any backend failure (timeout, rate limit, malformed response)."""


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


class LLMClient(ABC):
    @abstractmethod
    def generate(self, messages: list[dict], temperature: float = 0.2,
                 max_tokens: int = 2048) -> LLMResponse:
        ...
```

### File: `src/ai_test_gen/clients/openai_client.py`
```python
from __future__ import annotations
import time
from openai import OpenAI, APIError, APITimeoutError, RateLimitError
from ai_test_gen.clients.base import LLMClient, LLMResponse, LLMError


class OpenAIClient(LLMClient):
    def __init__(self, model: str = "gpt-4o-mini", base_url: str | None = None,
                 api_key: str | None = None):
        self.model = model
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def generate(self, messages, temperature=0.2, max_tokens=2048) -> LLMResponse:
        start = time.monotonic()
        try:
            resp = self._client.chat.completions.create(
                model=self.model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
        except (APIError, APITimeoutError, RateLimitError) as e:
            raise LLMError(str(e)) from e

        latency_ms = (time.monotonic() - start) * 1000
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text, model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency_ms,
        )
```

### File: `src/ai_test_gen/clients/__init__.py`
```python
from ai_test_gen.clients.base import LLMClient, LLMError, LLMResponse


def get_client(backend: str, model: str) -> LLMClient:
    if backend == "openai":
        from ai_test_gen.clients.openai_client import OpenAIClient
        return OpenAIClient(model=model)
    if backend == "vllm":
        from ai_test_gen.clients.vllm_client import VLLMClient
        return VLLMClient(model=model)
    if backend == "hf":
        from ai_test_gen.clients.hf_client import HFInferenceClient
        return HFInferenceClient(model=model)
    raise ValueError(f"unknown backend: {backend}")
```

**Verify (costs a few cents — this is your first real model call):**
```bash
python -c "
from ai_test_gen.extractor import extract_functions
from ai_test_gen.prompts import build_code_mode_prompt
from ai_test_gen.clients import get_client
from ai_test_gen.sanitizer import sanitize

spec = extract_functions('benchmark/functions/string_ops.py')[0]
client = get_client('openai', 'gpt-4o-mini')
resp = client.generate(build_code_mode_prompt(spec))
print(sanitize(resp.text))
"
```
Read the printed test file. Confirm it looks like a real pytest suite covering the categories from the prompt. This is the point to iterate on the prompt if the output looks weak — don't move on until it does.

**Commit:** `git add -A && git commit -m "Phase 1: extractor, prompts, sanitizer, openai client"`

---

## Phase 2 — Execution & Repair Loop (v2, ~4h)

### File: `src/ai_test_gen/runner.py`
```python
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FailureDetail:
    test_name: str
    traceback: str


@dataclass
class RunResult:
    passed: int
    failed: int
    errors: int
    xfailed: int
    branch_coverage: float
    uncovered_lines: list[tuple[int, str]]
    failure_details: list[FailureDetail]
    raw_ok: bool
    error_message: str = ""


def run_tests(module_source: str, test_code: str, timeout: int = 30) -> RunResult:
    tmpdir = Path(tempfile.mkdtemp(prefix="ai_test_gen_"))
    try:
        (tmpdir / "module_under_test.py").write_text(module_source)
        (tmpdir / "test_generated.py").write_text(test_code)
        cov_json = tmpdir / "cov.json"
        report_json = tmpdir / "report.json"

        cmd = [sys.executable, "-m", "pytest", "test_generated.py",
               "--cov=module_under_test", "--cov-branch",
               f"--cov-report=json:{cov_json.name}",
               "--json-report", f"--json-report-file={report_json.name}", "-q"]
        try:
            subprocess.run(cmd, cwd=tmpdir, timeout=timeout, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            return RunResult(0, 0, 0, 0, 0.0, [], [], raw_ok=False, error_message="execution_timeout")

        if not report_json.exists():
            return RunResult(0, 0, 0, 0, 0.0, [], [], raw_ok=False,
                              error_message="pytest_did_not_produce_report")

        report = json.loads(report_json.read_text())
        summary = report.get("summary", {})
        failure_details = []
        for test in report.get("tests", []):
            if test.get("outcome") == "failed":
                longrepr = str(test.get("call", {}).get("longrepr", ""))[:2000]
                failure_details.append(FailureDetail(test.get("nodeid", "?"), longrepr))

        branch_coverage = 0.0
        uncovered_lines: list[tuple[int, str]] = []
        if cov_json.exists():
            cov = json.loads(cov_json.read_text())
            mod = cov.get("files", {}).get("module_under_test.py", {})
            branch_coverage = mod.get("summary", {}).get("percent_covered", 0.0) / 100.0
            source_lines = module_source.splitlines()
            for ln in mod.get("missing_lines", []):
                if 1 <= ln <= len(source_lines):
                    uncovered_lines.append((ln, source_lines[ln - 1].strip()))

        return RunResult(
            passed=summary.get("passed", 0), failed=summary.get("failed", 0),
            errors=summary.get("error", 0), xfailed=summary.get("xfailed", 0),
            branch_coverage=branch_coverage, uncovered_lines=uncovered_lines,
            failure_details=failure_details, raw_ok=True,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
```

**Verify runner in isolation before wiring it to the LLM:**
```bash
python -c "
from ai_test_gen.runner import run_tests
module_source = 'def add(a, b):\n    return a + b\n'
test_code = 'from module_under_test import *\ndef test_add():\n    assert add(2,3) == 5\n'
r = run_tests(module_source, test_code)
print(r.passed, r.failed, r.branch_coverage, r.uncovered_lines)
"
```
Expect `1 0 1.0 []`.

### File: `src/ai_test_gen/repair.py`
```python
from __future__ import annotations
import json
from pathlib import Path

from ai_test_gen.clients.base import LLMClient, LLMError
from ai_test_gen.prompts import build_repair_prompt
from ai_test_gen.sanitizer import sanitize, SanitizationError
from ai_test_gen.runner import run_tests, RunResult


def generate_with_repair(client: LLMClient, initial_messages: list[dict],
                          module_source: str, temperature: float = 0.2,
                          target_coverage: float = 0.80, max_iters: int = 3,
                          log_path: Path | None = None) -> tuple[str, RunResult | None, int]:
    messages = initial_messages
    code = ""
    result: RunResult | None = None
    attempts_log = []

    for attempt in range(1, max_iters + 1):
        try:
            resp = client.generate(messages, temperature=temperature)
        except LLMError as e:
            attempts_log.append({"attempt": attempt, "error": str(e)})
            continue

        try:
            code = sanitize(resp.text)
        except SanitizationError as e:
            attempts_log.append({"attempt": attempt, "sanitization_error": str(e)})
            messages = initial_messages + [
                {"role": "assistant", "content": resp.text},
                {"role": "user", "content": f"That failed a static safety check: {e}. "
                                             f"Regenerate, fixing this, following all rules."},
            ]
            continue

        result = run_tests(module_source, code)
        attempts_log.append({"attempt": attempt, "passed": result.passed,
                              "failed": result.failed, "branch_coverage": result.branch_coverage})

        if result.failed == 0 and result.errors == 0 and result.branch_coverage >= target_coverage:
            break

        failure_summary = "\n".join(
            f"- {f.test_name}: {f.traceback[:300]}" for f in result.failure_details
        ) or "(no failing tests, but coverage target not met)"
        messages = build_repair_prompt(code, failure_summary, result.uncovered_lines)

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(attempts_log, indent=2))

    return code, result, len(attempts_log)
```

### File: `src/ai_test_gen/cli.py`
```python
from __future__ import annotations
import argparse
import csv
import json
import sys
import time
from pathlib import Path

from ai_test_gen.extractor import extract_functions
from ai_test_gen.prompts import build_code_mode_prompt, build_test_plan_prompt, CODE_MODE_VERSION
from ai_test_gen.clients import get_client
from ai_test_gen.repair import generate_with_repair
from ai_test_gen.runner import run_tests


def cmd_generate(args) -> int:
    functions = extract_functions(args.input, args.function)
    if not functions:
        print(f"No matching function found in {args.input}", file=sys.stderr)
        return 4

    module_source = Path(args.input).read_text()
    client = get_client(args.backend, args.model)
    exit_code = 0

    for spec in functions:
        messages = build_code_mode_prompt(spec)
        run_id = f"{spec.name}_{int(time.time())}"
        out_dir = Path(args.report_dir) / run_id

        code, result, attempts = generate_with_repair(
            client, messages, module_source,
            temperature=args.temperature, target_coverage=args.target_coverage,
            max_iters=args.max_iters, log_path=out_dir / "attempts.json",
        )

        if result is None:
            print(f"[{spec.name}] generation failed after {attempts} attempts", file=sys.stderr)
            exit_code = 1
            continue

        out_path = Path(args.out) if args.out else Path(f"tests/test_{spec.name}.py")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        header = f"# Generated by ai-test-gen | model={args.model} prompt={CODE_MODE_VERSION} temp={args.temperature}\n"
        out_path.write_text(header + code)

        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.json").write_text(json.dumps({
            "function": spec.name, "model": args.model, "attempts": attempts,
            "passed": result.passed, "failed": result.failed,
            "branch_coverage": result.branch_coverage,
        }, indent=2))

        status = "PASSED" if result.failed == 0 and result.errors == 0 else "NEEDS REVIEW"
        print(f"[{spec.name}] {status} | coverage={result.branch_coverage:.0%} "
              f"| attempts={attempts} | -> {out_path}")
        if result.failed > 0 or result.errors > 0:
            exit_code = 3

    return exit_code


def cmd_testplan(args) -> int:
    spec_text = args.spec if args.spec else Path(args.spec_file).read_text()
    client = get_client(args.backend, args.model)
    resp = client.generate(build_test_plan_prompt(spec_text), temperature=0.2)

    try:
        rows = json.loads(resp.text)
    except json.JSONDecodeError:
        print("Model did not return valid JSON:", resp.text, file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else Path(f"results/testplan.{args.format}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "csv":
        with out_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "category", "precondition",
                                               "steps", "expected_result", "priority"])
            w.writeheader()
            w.writerows(rows)
    else:
        lines = ["| ID | Category | Precondition | Steps | Expected | Priority |",
                  "|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['id']} | {r['category']} | {r['precondition']} | "
                         f"{r['steps']} | {r['expected_result']} | {r['priority']} |")
        out_path.write_text("\n".join(lines))

    print(f"Wrote {len(rows)} test cases to {out_path}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="ai-test-gen")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate")
    gen.add_argument("--input", required=True)
    gen.add_argument("--function")
    gen.add_argument("--backend", choices=["openai", "hf", "vllm"], default="openai")
    gen.add_argument("--model", default="gpt-4o-mini")
    gen.add_argument("--temperature", type=float, default=0.2)
    gen.add_argument("--target-coverage", type=float, default=0.80)
    gen.add_argument("--max-iters", type=int, default=3)
    gen.add_argument("--out")
    gen.add_argument("--report-dir", default="results")
    gen.set_defaults(func=cmd_generate)

    tp = sub.add_parser("testplan")
    tp.add_argument("--spec")
    tp.add_argument("--spec-file")
    tp.add_argument("--backend", choices=["openai", "hf", "vllm"], default="openai")
    tp.add_argument("--model", default="gpt-4o-mini")
    tp.add_argument("--format", choices=["csv", "markdown"], default="markdown")
    tp.add_argument("--out")
    tp.set_defaults(func=cmd_testplan)

    return parser


def main():
    args = build_parser().parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
```

**Verify (this is the real MVP checkpoint):**
```bash
ai-test-gen generate --input benchmark/functions/string_ops.py
cat tests/test_slugify.py
pytest tests/test_slugify.py -v
```
Expect: tests are generated, pytest passes, and the CLI printed a coverage percentage. Deliberately try `--target-coverage 0.99` to watch the repair loop fire more than once.

```bash
ai-test-gen testplan --spec "The login endpoint accepts email and password, locks the account for 15 minutes after 5 failed attempts, and returns a JWT valid for 24 hours." --format markdown
cat results/testplan.markdown
```

**Commit:** `git add -A && git commit -m "Phase 2: runner, repair loop, full CLI"`

---

## Phase 3 — Mutation Testing, Benchmark, Contamination Experiment (v3, ~6h)

### 1. Build the benchmark set (1.5h)

Add 15–20 small functions to `benchmark/functions/` (string ops, numeric boundary checks, a small stateful class, a sort/search function, a retry decorator). For each, add a deliberately buggy twin in `benchmark/buggy/` with the **same filename**. Example:

`benchmark/functions/clamp.py`:
```python
def clamp(value: float, low: float, high: float) -> float:
    """Return value restricted to [low, high]. Raises ValueError if low > high."""
    if low > high:
        raise ValueError("low must be <= high")
    return max(low, min(value, high))
```

`benchmark/buggy/clamp.py` (planted bug: off-by-one on the boundary):
```python
def clamp(value: float, low: float, high: float) -> float:
    """Return value restricted to [low, high]. Raises ValueError if low > high."""
    if low > high:
        raise ValueError("low must be <= high")
    if value == high:
        return high + 1  # BUG: should return high
    return max(low, min(value, high))
```

Repeat this pattern for the rest of your 15–20 functions before continuing.

### 2. File: `src/ai_test_gen/mutator.py`
```python
from __future__ import annotations
import ast
import copy

_COMPARISON_FLIPS = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE,
                      ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
_ARITHMETIC_FLIPS = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
_BOOL_FLIPS = {ast.And: ast.Or, ast.Or: ast.And}


def _find_mutable_nodes(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in _COMPARISON_FLIPS:
                    yield (node, i, "cmp")
        elif isinstance(node, ast.BinOp) and type(node.op) in _ARITHMETIC_FLIPS:
            yield (node, None, "arith")
        elif isinstance(node, ast.BoolOp) and type(node.op) in _BOOL_FLIPS:
            yield (node, None, "bool")
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            yield (node, None, "const_bool")


def generate_mutants(source: str, max_mutants: int = 30) -> list[str]:
    base_tree = ast.parse(source)
    targets = list(_find_mutable_nodes(base_tree))
    mutants = []
    for node, idx, kind in targets[:max_mutants]:
        tree_copy = copy.deepcopy(base_tree)
        pos = list(ast.walk(base_tree)).index(node)
        target = list(ast.walk(tree_copy))[pos]

        if kind == "cmp":
            target.ops[idx] = _COMPARISON_FLIPS[type(target.ops[idx])]()
        elif kind == "arith":
            target.op = _ARITHMETIC_FLIPS[type(target.op)]()
        elif kind == "bool":
            target.op = _BOOL_FLIPS[type(target.op)]()
        elif kind == "const_bool":
            target.value = not target.value

        ast.fix_missing_locations(tree_copy)
        try:
            mutants.append(ast.unparse(tree_copy))
        except Exception:
            continue
    return mutants


def mutation_score(source: str, test_code: str, run_tests_fn, max_mutants: int = 30) -> dict:
    mutants = generate_mutants(source, max_mutants=max_mutants)
    killed = 0
    for mutant_source in mutants:
        result = run_tests_fn(mutant_source, test_code)
        if result.failed > 0 or result.errors > 0:
            killed += 1
    total = len(mutants)
    return {"mutants_total": total, "mutants_killed": killed,
            "mutation_score": (killed / total) if total else None}
```

**Verify mutator on a known case:**
```bash
python -c "
from ai_test_gen.mutator import generate_mutants
src = 'def f(x):\n    if x < 5:\n        return True\n    return False\n'
mutants = generate_mutants(src)
print(len(mutants), 'mutants')
print([m for m in mutants if '<=' in m])
"
```

### 3. File: `benchmark/run_benchmark.py`
```python
"""Runs code-mode and spec-mode generation across the benchmark suite and
reports coverage / mutation score / planted-bug catch rate per mode."""
from pathlib import Path
import json
import matplotlib.pyplot as plt

from ai_test_gen.extractor import extract_functions
from ai_test_gen.prompts import build_code_mode_prompt, build_spec_mode_prompt
from ai_test_gen.clients import get_client
from ai_test_gen.repair import generate_with_repair
from ai_test_gen.runner import run_tests
from ai_test_gen.mutator import mutation_score

FUNCS_DIR = Path("benchmark/functions")
BUGGY_DIR = Path("benchmark/buggy")
RESULTS_DIR = Path("results/benchmark")


def run_mode(spec, module_source, mode, client):
    if mode == "code":
        messages = build_code_mode_prompt(spec)
    else:
        sig_hint = f"{spec.name}({', '.join(a for a, _ in spec.args)})"
        messages = build_spec_mode_prompt(spec.docstring or "", sig_hint)

    code, result, _ = generate_with_repair(client, messages, module_source)
    if result is None:
        return None
    mut = mutation_score(module_source, code, run_tests)
    return {"coverage": result.branch_coverage, "mutation_score": mut["mutation_score"], "code": code}


def catches_planted_bug(test_code: str, buggy_source: str) -> bool:
    result = run_tests(buggy_source, test_code)
    return result.failed > 0 or result.errors > 0


def main():
    client = get_client("openai", "gpt-4o-mini")
    rows = []

    for f in sorted(FUNCS_DIR.glob("*.py")):
        clean_source = f.read_text()
        buggy_path = BUGGY_DIR / f.name
        buggy_source = buggy_path.read_text() if buggy_path.exists() else None

        for spec in extract_functions(str(f)):
            for mode in ("code", "spec"):
                res = run_mode(spec, clean_source, mode, client)
                if res is None:
                    continue
                caught = catches_planted_bug(res["code"], buggy_source) if buggy_source else None
                rows.append({"function": spec.name, "mode": mode, **res, "caught_bug": caught})
                print(f"{spec.name} [{mode}] coverage={res['coverage']:.0%} "
                      f"mutation={res['mutation_score']} caught_bug={caught}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "summary.json").write_text(json.dumps(
        [{k: v for k, v in r.items() if k != "code"} for r in rows], indent=2))

    modes = ["code", "spec"]
    covs = [sum(r["coverage"] for r in rows if r["mode"] == m) /
            max(1, len([r for r in rows if r["mode"] == m])) for m in modes]
    plt.figure(); plt.bar(modes, covs); plt.title("Mean Branch Coverage by Mode")
    plt.ylabel("Coverage"); plt.savefig(RESULTS_DIR / "coverage_by_mode.png")

    bug_rates = []
    for m in modes:
        mode_rows = [r for r in rows if r["mode"] == m and r["caught_bug"] is not None]
        bug_rates.append(sum(1 for r in mode_rows if r["caught_bug"]) / len(mode_rows) if mode_rows else 0)
    plt.figure(); plt.bar(modes, bug_rates); plt.title("Planted Bug Catch Rate by Mode")
    plt.ylabel("Catch rate"); plt.savefig(RESULTS_DIR / "bug_catch_rate_by_mode.png")

    print("\nDone. See results/benchmark/ for summary.json and charts.")


if __name__ == "__main__":
    main()
```

**Verify:**
```bash
python benchmark/run_benchmark.py
open results/benchmark/coverage_by_mode.png   # or just check the file exists
cat results/benchmark/summary.json
```
This is a real API cost across ~15–20 functions × 2 modes — expect it to take several minutes and a few dollars on a cheap model. Confirm the spec-mode bug-catch rate is measurably different from code-mode; if they're identical, look at whether your buggy variants are subtle enough, or whether spec mode is accidentally leaking implementation details through the docstring.

Write your findings into `NOTES.md` now, while fresh — this is your interview answer for "what did you learn."

**Commit:** `git add -A && git commit -m "Phase 3: mutation testing, benchmark suite, contamination experiment"`

---

## Phase 4 — Tests, Local Backend, CI, README (v4, ~4h)

### 1. Tests for the tool itself

`tests/test_extractor.py`:
```python
from ai_test_gen.extractor import extract_functions

FIXTURE = '''
def add(a: int, b: int) -> int:
    """Add two numbers. Raises ValueError if either is negative."""
    if a < 0 or b < 0:
        raise ValueError("no negatives")
    return a + b
'''

def test_extract_basic(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text(FIXTURE)
    specs = extract_functions(str(f))
    assert len(specs) == 1
    assert specs[0].name == "add"
    assert specs[0].returns == "int"
    assert "ValueError" in specs[0].raises
```

`tests/test_sanitizer.py`:
```python
import pytest
from ai_test_gen.sanitizer import sanitize, SanitizationError

def test_sanitize_strips_fences():
    raw = "```python\ndef test_x():\n    assert True\n```"
    assert "def test_x" in sanitize(raw)

def test_sanitize_rejects_disallowed_import():
    with pytest.raises(SanitizationError):
        sanitize("import os\ndef test_x(): pass")

def test_sanitize_rejects_syntax_error():
    with pytest.raises(SanitizationError):
        sanitize("def test_x(:\n pass")

def test_sanitize_rejects_eval():
    with pytest.raises(SanitizationError):
        sanitize("def test_x():\n    eval('1+1')")
```

`tests/test_mutator.py`:
```python
from ai_test_gen.mutator import generate_mutants

def test_generates_comparison_mutant():
    source = "def f(x):\n    if x < 5:\n        return True\n    return False\n"
    mutants = generate_mutants(source)
    assert any("<=" in m for m in mutants)
```

`tests/test_pipeline_mocked.py` (no live API calls — safe for CI):
```python
from ai_test_gen.clients.base import LLMClient, LLMResponse
from ai_test_gen.prompts import build_code_mode_prompt
from ai_test_gen.extractor import extract_functions
from ai_test_gen.repair import generate_with_repair

CANNED_TEST = '''```python
import pytest
from module_under_test import *

def test_add_happy_path():
    assert add(2, 3) == 5

def test_add_negative_raises():
    with pytest.raises(ValueError):
        add(-1, 2)
```'''

class MockClient(LLMClient):
    def generate(self, messages, temperature=0.2, max_tokens=2048):
        return LLMResponse(text=CANNED_TEST, model="mock")

def test_pipeline_end_to_end(tmp_path):
    module_source = ('def add(a, b):\n'
                      '    """Add two numbers. Raises ValueError if negative."""\n'
                      '    if a < 0 or b < 0:\n'
                      '        raise ValueError("no negatives")\n'
                      '    return a + b\n')
    mod_file = tmp_path / "mod.py"
    mod_file.write_text(module_source)
    spec = extract_functions(str(mod_file))[0]
    messages = build_code_mode_prompt(spec)
    code, result, attempts = generate_with_repair(MockClient(), messages, module_source)
    assert result is not None
    assert result.failed == 0
```

**Verify:** `pytest tests/ -v` — all green, zero API calls made.

### 2. Local vLLM backend (optional, if you have GPU access)

`src/ai_test_gen/clients/vllm_client.py`:
```python
from ai_test_gen.clients.openai_client import OpenAIClient

class VLLMClient(OpenAIClient):
    """vLLM serves an OpenAI-compatible endpoint -- point the OpenAI SDK
    at it. api_key is required by the SDK but ignored by vLLM."""
    def __init__(self, model: str, base_url: str = "http://localhost:8000/v1"):
        super().__init__(model=model, base_url=base_url, api_key="not-needed")
```

```bash
pip install vllm
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --max-model-len 8192
# in another terminal:
ai-test-gen generate --input benchmark/functions/string_ops.py --backend vllm --model Qwen/Qwen2.5-Coder-7B-Instruct
```
Record tokens/sec, latency, and $/1000-functions vs. hosted for your README.

### 3. File: `.github/workflows/ci.yml`
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v
```

**Verify:** push to GitHub, confirm the Actions tab shows a green run.

### 4. README

Lead with your Phase 3 numbers table and both PNG charts, then a short architecture diagram (copy from `02_TRD.md` §1), then usage examples pulled straight from the Verify steps above.

**Commit:** `git add -A && git commit -m "Phase 4: tool tests, vLLM backend, CI, README"`

---

## Phase 5 — Full End-to-End Verification (make sure it's actually "done")

Simulate what happens if you had to demo this cold, on a machine that's never seen it:

```bash
git clone <your-repo-url> /tmp/verify-clone && cd /tmp/verify-clone
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export OPENAI_API_KEY="sk-..."

pytest tests/ -v                                          # tool's own tests, all pass, no API calls
ai-test-gen generate --input benchmark/functions/string_ops.py   # real generation + repair loop
pytest tests/test_slugify.py -v                            # generated tests actually pass
ai-test-gen testplan --spec "..." --format csv              # test plan mode works
python benchmark/run_benchmark.py                           # full benchmark reproduces your numbers
```

If every one of those commands works on a clean clone with nothing but the README's instructions, the project is done and demo-ready. If any step requires a manual fix you forgot to document, fix the README or the code — not just your memory of how it works.

## Definition of Done

- [ ] `pytest tests/` passes with zero live API calls
- [ ] `generate` converges (passes + hits target coverage) on most benchmark functions within 3 attempts
- [ ] `benchmark/run_benchmark.py` reproduces coverage, mutation score, and bug-catch-rate numbers, both modes
- [ ] `NOTES.md` documents at least 2 concrete prompt iterations and what changed
- [ ] CI is green on a fresh push
- [ ] README leads with real numbers and both charts
- [ ] A clean clone + the README's own instructions reproduces everything above with no undocumented manual steps
