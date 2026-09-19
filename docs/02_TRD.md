# Technical Requirements Document (TRD)
## AI-Powered Test Case Generator

**Companion to:** `01_PRD.md`
**Version:** 1.0

---

## 1. Architecture Overview

```
                         ┌────────────────────┐
   .py file / spec text │       CLI (cli.py)  │
   ───────────────────▶ │  generate|testplan  │
                         │  benchmark|report   │
                         └─────────┬───────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     ▼                            ▼
            ┌────────────────┐           ┌──────────────────┐
            │   Extractor     │           │  Spec Parser      │
            │ (ast → FuncSpec)│           │ (raw text passthr)│
            └────────┬────────┘           └────────┬──────────┘
                     └───────────────┬──────────────┘
                                     ▼
                          ┌─────────────────────┐
                          │   Prompt Builder     │
                          │ (templates + rules   │
                          │  + few-shot)         │
                          └──────────┬───────────┘
                                     ▼
                          ┌─────────────────────┐
                          │   LLM Client (ABC)   │
                          │ OpenAIClient          │
                          │ HFInferenceClient     │
                          │ VLLMClient            │
                          └──────────┬───────────┘
                                     ▼
                          ┌─────────────────────┐
                          │     Sanitizer        │
                          │ (ast.parse gate,      │
                          │  import whitelist)    │
                          └──────────┬───────────┘
                                     ▼
                          ┌─────────────────────┐
                          │       Writer         │
                          │ tests/test_<mod>.py   │
                          └──────────┬───────────┘
                                     ▼
                          ┌─────────────────────┐
                          │   Runner (subprocess) │
                          │ pytest + coverage.py  │
                          │ JSON report, timeout  │
                          └──────────┬───────────┘
                                     │
                        pass + coverage OK?
                        │no                │yes
                        ▼                  ▼
             ┌────────────────────┐  ┌───────────────────┐
             │   Repair Loop        │  │     Mutator        │
             │ (feed failures +     │  │ (ast.NodeTransformer│
             │  uncovered lines     │  │  mutation testing)  │
             │  back into prompt,   │  └─────────┬───────────┘
             │  max 3 iterations)   │            ▼
             └──────────┬───────────┘  ┌───────────────────┐
                        │              │     Reporter         │
                        └─────────────▶│ coverage %, mutation  │
                                       │ score, markdown/JSON  │
                                       └───────────────────────┘
```

Optional (Phase 4, see PRD Non-Goals for scope limits): a thin FastAPI wrapper + SQLite store so results can be browsed instead of re-read from disk. Fully optional — the CLI + JSON/Markdown reports are sufficient to demonstrate the project. See `03_API_AND_SCHEMA_SPEC.md`.

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Matches project domain; `ast`, `tomllib` stdlib support |
| Parsing | `ast` (stdlib) | No regex parsing of source — correctness and credibility |
| Test execution | `pytest`, `pytest-json-report`, `coverage.py` (branch mode) | Industry standard, machine-readable output |
| Mutation testing | Custom `ast.NodeTransformer` mutator (primary) + optional `mutmut` cross-check | Custom version is small, explainable, and a stronger interview artifact than "I imported a library" |
| LLM backends | `openai` SDK, `huggingface_hub` InferenceClient, `vllm` (self-hosted, OpenAI-compatible) | Covers hosted + local, one interface |
| CLI | `click` or `argparse` (argparse is zero-dependency — prefer it unless subcommand ergonomics matter) | Simplicity |
| Optional API | `FastAPI` + `SQLite` (via `sqlite3` or `SQLModel`) | Only if Phase 4 time allows |
| CI | GitHub Actions | Free, standard, shows automation instinct |
| Config | `pydantic` (or dataclasses) for settings validation | Type safety on config values (temperature, model name, targets) |

Keep dependencies minimal. Every added library should be justifiable in an interview answer.

## 3. Component Specifications

### 3.1 Extractor (`extractor.py`)
- Input: file path, optional function name filter.
- Output: list of `FunctionSpec` dataclasses:
  ```python
  @dataclass
  class FunctionSpec:
      name: str
      args: list[tuple[str, str | None]]   # (name, type annotation)
      returns: str | None
      docstring: str | None
      source: str
      is_async: bool
      raises: list[str]                     # exception type names
      module_path: str
  ```
- Must walk the full `ast.Module`, not just top-level defs (support methods inside classes — track `ClassDef` parent for qualified names like `ClassName.method_name`).
- Must not execute the target file (static analysis only — never `import` untrusted code before sanitization).

### 3.2 Prompt Builder (`prompts.py`)
- Templates versioned as `PROMPT_V1`, `PROMPT_V2`, etc. — never mutate a template in place; log which version produced which result (traceability for the NOTES.md experiment log).
- Three template families: `CODE_MODE`, `SPEC_MODE`, `TEST_PLAN`, `REPAIR`.
- Few-shot example(s) stored as constants, not regenerated per call.
- Builder function signature: `build_prompt(spec: FunctionSpec | str, mode: Literal["code","spec","testplan","repair"], repair_context: RepairContext | None = None) -> list[dict]` returning chat-format messages.

### 3.3 LLM Client Interface (`clients/base.py`)
```python
class LLMClient(ABC):
    @abstractmethod
    def generate(self, messages: list[dict], temperature: float = 0.2,
                 max_tokens: int = 2048) -> LLMResponse: ...

@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
```
- `OpenAIClient`, `HFInferenceClient`, `VLLMClient` each implement `generate`.
- `VLLMClient` reuses the OpenAI SDK pointed at `base_url=http://localhost:8000/v1` — same request shape, near-zero extra code.
- Client selection via config/CLI flag: `--backend openai|hf|vllm`.
- All clients must raise a common `LLMError` on failure (timeout, rate limit, malformed response) so upstream retry logic doesn't need backend-specific handling.

### 3.4 Sanitizer (`sanitizer.py`)
- Strip markdown code fences.
- `ast.parse()` the result — reject on `SyntaxError`.
- Walk for `Import`/`ImportFrom`; reject anything outside an explicit allowlist (`pytest`, the module under test, `math`, `typing`, `re`, stdlib data-structure modules as needed — never `os`, `subprocess`, `socket`, `shutil`, dynamic `eval`/`exec`).
- Reject any `Call` node targeting `eval`, `exec`, `__import__`, `open` (unless explicitly enabled for a specific benchmark case).
- Return sanitized source string or raise `SanitizationError` with a specific reason (feeds into repair loop as "your last output failed static safety checks: <reason>").

### 3.5 Runner (`runner.py`)
- Write sanitized test file to a working directory (`results/<run_id>/test_generated.py`).
- Execute: `pytest <file> --cov=<module> --cov-branch --cov-report=json --json-report --json-report-file=report.json`, via `subprocess.run(..., timeout=30, cwd=<isolated dir>)`.
- Parse both JSON reports into a `RunResult`:
  ```python
  @dataclass
  class RunResult:
      passed: int
      failed: int
      errors: int
      xfailed: int
      branch_coverage: float
      uncovered_lines: list[tuple[int, str]]   # (line_no, source_text)
      failure_details: list[FailureDetail]      # test name, traceback (truncated)
  ```
- Isolation: run in a fresh temp directory per attempt; do not let generated tests import each other across runs. Prefer running inside a subprocess with `--network none`-equivalent restriction if using Docker (stretch goal, not required for MVP).

### 3.6 Repair Loop (`repair.py`)
- `for attempt in range(MAX_ITERS)`; default `MAX_ITERS = 3`.
- Stop condition: all tests pass (or intentionally `xfail`) AND branch coverage ≥ `TARGET_COVERAGE` (default 80%).
- On failure, classify each failing test:
  - **Test-side bug** (assertion doesn't match a clear, unambiguous docstring contract) → included in repair prompt for correction.
  - **Suspected source bug** (test contradicts explicit documented behavior) → excluded from repair prompt, flagged in final report as `suspected_source_bug`, not silently dropped or "fixed" by loosening the assertion.
- Feed `uncovered_lines` as actual source text, not bare line numbers.
- Log every attempt's prompt version, diff from previous attempt, and resulting `RunResult` to `results/<run_id>/attempts.jsonl` — this file is the evidence for "I iterated" in the interview.

### 3.7 Mutator (`mutator.py`)
- `ast.NodeTransformer` subclasses, one per operator:
  - `ComparisonMutator`: `<`↔`<=`, `>`↔`>=`, `==`↔`!=`
  - `ArithmeticMutator`: `+`↔`-`, `*`↔`/`
  - `BooleanMutator`: `and`↔`or`
  - `ConstantMutator`: negate/zero numeric constants, flip `True`/`False`
  - `ReturnMutator`: replace return expression with `None`
- Generate one mutant per applicable AST node (don't combine mutations — one mutation per mutant is standard mutation-testing practice).
- For each mutant: write mutated source to a temp module, run the *unmodified* generated test suite against it, record kill/survive.
- `mutation_score = killed / total_mutants` (exclude equivalent mutants only if you can prove equivalence — for a portfolio project, it's fine to report raw score and note the equivalent-mutant caveat rather than trying to detect them).

### 3.8 Reporter (`reporter.py`)
- Aggregates `RunResult` + mutation results + benchmark comparisons into:
  - `results/<run_id>/report.json` (machine-readable, full detail)
  - `results/<run_id>/report.md` (human-readable summary table)
  - `results/benchmark/summary.md` + two charts (coverage by mode, bug-catch-rate by mode) generated via `matplotlib`, saved as PNG.

### 3.9 CLI (`cli.py`)
See `03_API_AND_SCHEMA_SPEC.md` §2 for the exact command/flag spec.

## 4. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Security** | No generated code executes without passing the Sanitizer. Subprocess execution always has a timeout (default 30s). No network access from within generated test execution. |
| **Reliability** | Any LLM/network failure must not crash the CLI — catch `LLMError`, log, and either retry (bounded) or exit with a clear error message and non-zero exit code. |
| **Reproducibility** | Every run logs: model name, model version/hash if available, temperature, prompt template version, timestamp. Stored alongside the generated test file as a header comment and in `report.json`. |
| **Performance** | Single-function generation (excluding LLM latency) should add < 1s of local overhead (parsing, sanitizing, running). Benchmark run of 20 functions should complete in a documented wall-clock time, reported in the README. |
| **Portability** | No hardcoded paths; runnable via `pip install -e .` + entry point script on macOS/Linux (Windows best-effort, not required). |
| **Cost control** | Local caching of (prompt hash → response) during development to avoid repeated billed calls while iterating on the harness. |

## 5. Error Handling Strategy

| Failure | Handling |
|---|---|
| LLM API timeout/rate limit | Exponential backoff, max 3 retries, then fail the attempt (counts against `MAX_ITERS`) |
| Model returns non-code / refuses | Sanitizer rejects (fails `ast.parse`), treated as a failed attempt, retried with a stricter reminder prompt |
| Disallowed import | Sanitizer rejects with specific reason fed back into repair prompt |
| pytest subprocess hangs | `subprocess.run(timeout=...)` kills it; counts as a failed attempt with reason `"execution_timeout"` |
| Ambiguous expected behavior | Model instructed to emit `xfail(reason=...)` — not an error, a designed output state |
| Mutation testing takes too long on large functions | Cap mutants per function (e.g., first 30 generated) and note the cap in the report |

## 6. Testing Strategy for the Tool Itself

The tool needs its own test suite — shipping an untested test-generator is a credibility gap.

- Unit tests for `extractor.py` against fixture files with known expected `FunctionSpec` output.
- Unit tests for `sanitizer.py` with adversarial inputs (disallowed imports, `eval`, malformed syntax, fence variations).
- Unit tests for `mutator.py` verifying each mutation operator produces the expected AST change on a fixture.
- Integration test for the full pipeline using a **mocked** `LLMClient` (return canned responses) so CI doesn't require API keys or cost money.
- One real end-to-end smoke test gated behind an environment variable (`RUN_LIVE_LLM_TESTS=1`) so it's opt-in, not part of default CI.

## 7. CI Pipeline (GitHub Actions)

```yaml
# .github/workflows/ci.yml (concept — see implementation guide for full file)
on: [push, pull_request]
jobs:
  test:
    steps:
      - checkout
      - setup-python (3.11)
      - pip install -e .[dev]
      - run unit tests (pytest, mocked LLM)
      - run benchmark in "replay" mode using cached fixture responses (no live API calls in CI)
      - assert mean mutation score on cached benchmark ≥ threshold (regression gate)
      - upload report.md / charts as build artifacts
```

Keep live-API benchmark runs manual/local (cost + flakiness); CI replays cached responses to catch regressions in the *harness* (sanitizer, runner, mutator), which is what you actually control.

## 8. Directory Structure

```
ai-test-generator/
├── pyproject.toml
├── README.md
├── NOTES.md                  # prompt version history + experiment log
├── src/
│   └── ai_test_gen/
│       ├── extractor.py
│       ├── prompts.py
│       ├── clients/
│       │   ├── base.py
│       │   ├── openai_client.py
│       │   ├── hf_client.py
│       │   └── vllm_client.py
│       ├── sanitizer.py
│       ├── runner.py
│       ├── repair.py
│       ├── mutator.py
│       ├── reporter.py
│       └── cli.py
├── benchmark/
│   ├── functions/             # 15–20 clean target functions
│   ├── buggy/                 # same functions, planted bugs
│   └── golden/                # hand-written reference test suites
├── results/                   # generated output, gitignored except sample
├── tests/                     # tests OF the tool
│   ├── fixtures/
│   ├── test_extractor.py
│   ├── test_sanitizer.py
│   ├── test_mutator.py
│   └── test_pipeline_mocked.py
└── .github/workflows/ci.yml
```
