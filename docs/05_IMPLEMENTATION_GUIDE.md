# Implementation Guide — `testgen`

Eight phases. Each has a **definition of done** — do not move on until it's met, and
**commit at every phase boundary** so your git history reads like an engineering log
rather than one "initial commit" dump. Interviewers do look.

| Phase | What | Time |
|---|---|---|
| 0 | Scaffold, config, fake client | 1.5 h |
| 1 | Extractor | 1.5 h |
| 2 | Prompts + real backend | 2 h |
| 3 | Sanitizer + sandboxed runner | 2.5 h |
| 4 | Repair loop + SQLite store | 3 h |
| 5 | Benchmark corpus + golden baseline | 4 h |
| 6 | Mutation engine + planted bugs | 4 h |
| 7 | Plan mode, vLLM, CI gate, README | 4 h |

**~22 hours.** Phases 0–4 give you a working tool (~10 h, one weekend). Phases 5–6 are
what make it interview-proof. Phase 7 is the NVIDIA-specific differentiator.

---

## Phase 0 — Scaffold (1.5 h)

```bash
mkdir ai-test-generator && cd ai-test-generator
git init
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

`pyproject.toml`:

```toml
[project]
name = "testgen"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "typer>=0.12", "pydantic>=2.7", "pydantic-settings>=2.3",
  "openai>=1.40", "pytest>=8.2", "pytest-json-report>=1.5",
  "coverage>=7.5", "matplotlib>=3.9", "rich>=13.7",
]

[project.optional-dependencies]
dev = ["pytest-cov", "ruff", "mypy"]

[project.scripts]
testgen = "testgen.cli:app"

[tool.testgen]
backend = "openai"
model = "gpt-4o-mini"
temperature = 0.2
max_iterations = 3
target_coverage = 0.85
db_path = ".testgen/results.db"
```

```bash
pip install -e ".[dev]"
```

Create the module tree from `02_TRD.md` §3. Then three things, in this order:

1. **`models.py`** — paste the pydantic models from `03_DATA_AND_API_SPEC.md` §2. Types
   first means every later phase is guided by the compiler and your editor.
2. **`config.py`** — `Settings(BaseSettings)` with `env_prefix="TESTGEN_"`, loading
   `[tool.testgen]` from `pyproject.toml` as the file layer.
3. **`clients/base.py` + a `FakeLLMClient`** that returns a canned test file from
   `tests/fixtures/`.

> **Build the fake client on day one.** Every subsequent phase is developed and tested
> against it: no API key, no cost, no latency, fully deterministic. This is also what lets
> your own CI run the whole pipeline for free. It is the highest-leverage 20 minutes in
> the project.

**Done when:** `testgen --help` prints, and a throwaway script runs
`FakeLLMClient().generate(...)` and prints canned code.

---

## Phase 1 — Extractor (1.5 h)

Implement `extract_functions(path) -> list[FunctionSpec]` per `02_TRD.md` §3.1.

```python
import ast, hashlib

class _Extractor(ast.NodeVisitor):
    def __init__(self, module_path: str, src: str):
        self.module_path, self.src, self.specs, self._class = module_path, src, [], None

    def visit_ClassDef(self, node):
        prev, self._class = self._class, node.name
        self.generic_visit(node)
        self._class = prev

    def visit_FunctionDef(self, node):      # alias visit_AsyncFunctionDef = visit_FunctionDef
        src = ast.unparse(node)
        self.specs.append(FunctionSpec(
            module_path=self.module_path,
            qualname=f"{self._class}.{node.name}" if self._class else node.name,
            signature=self._render_signature(node),
            params=self._params(node),
            returns=ast.unparse(node.returns) if node.returns else None,
            docstring=ast.get_docstring(node),
            source=src,
            source_hash=hashlib.sha256(src.encode()).hexdigest(),
            raises=self._raises(node),
            decorators=[ast.unparse(d) for d in node.decorator_list],
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_method=self._class is not None,
            loc=(node.end_lineno or node.lineno) - node.lineno + 1,
            complexity=self._complexity(node),
        ))
        # do NOT generic_visit here — skip nested closures
```

Three details that cause bugs if you skip them:

- `visit_ClassDef` must save/restore the class name, or nested classes mislabel qualnames.
- Don't recurse into function bodies, or you'll extract inner helper closures as targets.
- `_raises` should collect `ast.Raise` nodes and pull the exception *name*: handle
  `raise ValueError("x")` (`Call` → `func.id`) and bare `raise ValueError` (`Name` → `id`).

**Done when:** running it on a fixture with a module function, a class method, an async
function, a decorated function, a nested class, and three `raise` forms produces correct
specs — verified by unit tests you write now, not later.

```bash
git commit -m "feat(extractor): ast-based function spec extraction"
```

---

## Phase 2 — Prompts and a real backend (2 h)

**Step 2.1** — Write `prompts/v1_code.txt` as a deliberately naive prompt
("Write pytest tests for this function:"). Keep it forever. It's the baseline for E2 in
your evaluation plan, and "here's what naive prompting produces" is a great demo moment.

**Step 2.2** — Write `v3_code.txt` and `v3_spec.txt` with all four structural elements
from `02_TRD.md` §3.2. Spend real time here; this is the core craft of the project. The
ambiguity rule is mandatory:

```
AMBIGUITY RULE: If the specification does not state what should happen for
an input, do NOT guess. Emit the test but mark it:
    @pytest.mark.xfail(reason="spec ambiguous: <what is unspecified>")
Never invent expected behavior that the specification does not state.
```

**Step 2.3** — `PromptBuilder.build(request) -> Prompt`, with a `PROMPT_VERSION` registry
mapping version string → template file. Never inline a prompt in Python.

**Step 2.4** — `OpenAIClient`. Record tokens, latency, cost. Add `ResponseCache` keyed by
`sha256(prompt + model + temperature)` backed by files under `.testgen/cache/`.

**Step 2.5** — Wire `testgen generate` end to end: extract → build → generate → write file
with a provenance header:

```python
HEADER = '''"""Auto-generated by testgen {version}.
model={model} prompt_version={pv} temperature={temp} mode={mode}
generated_at={ts} run_id={run_id}
REVIEW BEFORE COMMITTING. Generated tests may encode existing defects as expected behavior.
"""
'''
```

That warning line is not decoration. It's the project's thesis, stamped on every artifact.

**Done when:** `testgen generate examples/clamp.py --mode spec` writes a plausible
`tests/generated/test_clamp.py`. It may not run yet — that's Phase 3.

---

## Phase 3 — Sanitizer and sandboxed runner (2.5 h)

**Step 3.1 — Sanitizer.** Five ordered gates from `02_TRD.md` §3.4, each returning a
`SanitizeStatus` and detail string. Write the unit tests first — this is a pure function
with adversarial inputs, which is the ideal TDD case. Your adversarial corpus:

```
fenced python / fenced plain / unfenced / prose before code / prose after code /
empty / only a comment / import os / from os import path / __import__("os") /
eval("...") / open("/etc/passwd") / subprocess.run / no test_ functions /
syntax error / non-UTF8 bytes
```

**Step 3.2 — Runner.** Copy the module + generated test into a
`tempfile.TemporaryDirectory`, run the pytest command from `02_TRD.md` §3.5, parse
`report.json` and `coverage.json`.

Non-obvious pieces:

- Strip API keys from the subprocess env. Generated code runs with your environment
  otherwise.
- `timeout=` on `subprocess.run` doesn't kill grandchildren. Use
  `start_new_session=True` and `os.killpg` on timeout.
- Map coverage's missing line numbers back to **source text** — store
  `[{"line": 47, "source": "    if retries > MAX: raise TimeoutError"}]`. The repair loop
  needs the text, not the numbers.
- Parse `--cov-branch` output for branch data specifically: `coverage.json` gives
  `summary.covered_branches` / `num_branches` per file.

**Step 3.3** — Optional `--sandbox docker` path. Same command inside
`docker run --rm --network none --memory 512m --pids-limit 128 -v <tmp>:/work -w /work`.
Even if you rarely use it, having it is a real security answer.

**Done when:** `testgen generate examples/clamp.py --mode spec` prints a table: tests
collected/passed/failed, line and branch coverage, duration. And your sanitizer unit tests
are green against the full adversarial corpus.

```bash
git commit -m "feat(safety): sanitizer gates + sandboxed pytest runner"
```

---

## Phase 4 — Repair loop and store (3 h)

**Step 4.1 — Store.** `store.py` with the DDL from `03_DATA_AND_API_SPEC.md` §1 as
`migrations/001_init.sql`, applied at startup against `schema_meta`. WAL mode, foreign
keys on. DAO methods: `create_run`, `upsert_target`, `record_generation`,
`record_execution`, `record_cases`, `record_metric`, `finish_run`.

**Step 4.2 — Repair loop.**

```python
for iteration in range(cfg.max_iterations):
    result = generate_and_execute(spec, mode, iteration, repair_ctx)
    store.record_generation(run_id, result)

    if result.sanitize_status is not OK:
        repair_ctx = RepairContext(previous_code=result.raw_response,
                                   sanitize_error=result.sanitize_detail)
        continue

    store.record_execution(result.execution)
    if result.execution.counts.failed == 0 and \
       result.execution.branch_coverage >= cfg.target_coverage:
        break

    repair_ctx = build_repair_context(result)   # failures + uncovered source text
```

**Step 4.3 — Failure classification** per `02_TRD.md` §3.6. Keep the heuristic simple and
be honest in the README that it is a heuristic, not a solved problem. A reasonable
implementation: if the assertion's expected value appears verbatim in the docstring and
the actual value doesn't, classify `suspected_source_defect`.

**Step 4.4 — Reporter.** `report.md` + `report.json`, and a rich console table.

**Done when:** a function that needs two iterations converges, and
`sqlite3 .testgen/results.db "select * from v_run_summary"` returns a populated row.

```bash
git commit -m "feat(loop): coverage-driven repair loop with sqlite run history"
```

**You now have a working product.** Stop here if you must — it's already a solid project.
Everything after this is what makes it a *strong* one.

---

## Phase 5 — Benchmark and golden baseline (4 h)

**Step 5.1** — Write the 20 functions from `04_EVALUATION_PLAN.md` §2 in
`benchmark/functions/`. **Write each docstring before its implementation.** Leave 3–4
behaviors deliberately unspecified.

**Step 5.2** — Hand-write `benchmark/golden/test_*.py` for all 20. Four hours you will be
tempted to skip; don't. Every headline number in your README is a ratio against this
baseline, and without it you're reporting absolutes that mean nothing.

**Step 5.3** — `testgen bench` command: iterate targets × modes × seeds, persist
everything, aggregate run-level metrics into the `metric` table.

**Step 5.4** — `testgen trend` + matplotlib charts into `results/charts/`.

**Done when:** `testgen bench --modes code,spec` completes 40 generations and writes
`results/RESULTS.md` with a per-target table.

---

## Phase 6 — Mutation engine and planted bugs (4 h)

**Step 6.1** — `mutation.py`: one `NodeTransformer` per operator from `02_TRD.md` §3.7.
Pattern for each mutant site:

```python
class RORMutator(ast.NodeTransformer):
    SWAPS = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE,
             ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
    def __init__(self, target_index): self.i, self.n = target_index, 0
    def visit_Compare(self, node):
        self.generic_visit(node)
        for k, op in enumerate(node.ops):
            if type(op) in self.SWAPS:
                if self.n == self.i:
                    node.ops[k] = self.SWAPS[type(op)]()
                    self.n += 1
                    return node
                self.n += 1
        return node
```

Two passes: count sites, then generate one mutant per site index. Cap at `--max-mutants`.

**Step 6.2** — Kill detection: write the mutated module into the temp workdir, re-run the
generated suite, record `killed` / `survived` / `timeout` / `error` per mutant and which
test did the killing.

**Step 6.3** — Cross-validate against `mutmut` on 3 functions. Report agreement. This
preempts the obvious challenge to a self-written scorer.

**Step 6.4** — `benchmark/buggy/`: one buggy variant per function, **clean docstring
retained**. Record the unified diff in `planted_bug`.

**Step 6.5** — The headline experiment:

```bash
testgen bench --planted-bugs --modes code,spec --mutation --label "E1-mode-comparison"
```

A planted bug is **detected** when ≥1 non-xfail test fails against the buggy variant.

**Done when:** you can state, with a chart, the planted-bug detection rate for each mode —
and ideally break it down by bug class.

```bash
git commit -m "feat(eval): mutation engine + planted-bug defect detection benchmark"
```

---

## Phase 7 — Plan mode, GPU, CI gate, README (4 h)

**Step 7.1 — Plan mode (45 min).** `v3_plan.txt` prompt, JSON output per
`03_DATA_AND_API_SPEC.md` §2.1, CSV and Markdown exporters. Force category coverage by
listing the eight categories explicitly and requiring ≥1 case per applicable category.
Validate the JSON with pydantic; retry once on a parse failure.

**Step 7.2 — vLLM backend (1 h).**

```bash
pip install vllm
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --max-model-len 8192 --port 8000
export TESTGEN_BACKEND=vllm TESTGEN_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
export TESTGEN_BASE_URL=http://localhost:8000/v1
testgen bench --modes code,spec --label "E3-local-qwen"
```

`VLLMClient` subclasses `OpenAIClient` with a different `base_url` and `cost_usd=0`.
Then **measure and record**: p50/p95 latency, tokens/sec, VRAM, and — the important one —
serial vs concurrent throughput. Submit all 20 requests with a thread pool or `asyncio`
and watch continuous batching earn its keep. Put the speedup factor in your README.

No GPU? Use a Colab T4 with a smaller model, or run `llama.cpp` on CPU and report the
honest latency. Having *tried* self-hosted inference is what matters.

**Step 7.3 — CI gate (45 min).** `gate.py` reads run-level metrics, compares to thresholds
and/or the last green run, exits 1 on breach with a clear breach list. Then a GitHub
Actions workflow that runs your own unit tests plus a `FakeLLMClient` end-to-end pipeline
on every push — free, deterministic, no secrets.

**Step 7.4 — README (1.5 h).** Structure, in order:

1. One-sentence description + the warning that generated tests can encode existing bugs
2. **Results table and the two key charts, above the fold**
3. 30-second demo (asciinema or a GIF — worth the 20 minutes)
4. Quickstart: install, run on one function, run the benchmark
5. How it works (the architecture diagram from the TRD)
6. Evaluation methodology, linking `04_EVALUATION_PLAN.md`
7. **Threats to validity** — verbatim from the eval plan
8. Limitations and non-goals
9. What I'd do next

Lead with numbers:

> 20 functions · mean branch coverage 0.87 · mutation score 0.71 vs 0.84 hand-written ·
> planted-bug detection 0.73 (spec mode) vs 0.40 (code mode) · 2.3 s/function on a local
> 7B model · $0.00 marginal cost.

---

## Ordering rules

- **Never** execute generated code before the sanitizer exists. Phase 3 before any real
  model output touches your machine.
- The fake client (Phase 0) is a prerequisite for everything — build it first.
- Golden baseline (5.2) before mutation (Phase 6); the baseline is what mutation scores
  are compared against.
- Don't build the REST API until everything else is done. It adds no interview value over
  a well-designed CLI.

## Common failure modes and fixes

| Symptom | Cause | Fix |
|---|---|---|
| Model returns prose + code | Weak output contract | Strengthen the "ONLY code in one fenced block" instruction; add a one-shot example |
| Tests import the module wrongly | Model guesses the import path | Pass `module_name` explicitly in the prompt and show the exact import line |
| Floats compared with `==` | Missing constraint | Explicit `pytest.approx` rule; add to few-shot |
| Tests for private helpers | Extractor included `_name` | Exclude private by default |
| Coverage stuck below target | Model can't see what's missing | Send uncovered **source text**, not line numbers |
| Repair loop oscillates | Model rewrites everything each time | Instruct "keep passing tests unchanged; add or fix only what is listed" |
| Mutation run takes forever | Too many mutants | Cap per function; run mutation only on the final iteration |
| Buggy variant passes everything | Exactly H2 — this is the finding | Don't fix it. Measure it. |

## Pre-submission checklist

- [ ] README leads with results and charts
- [ ] Repo has its own CI badge, green, running without secrets
- [ ] `testgen`'s own test coverage ≥85% branch
- [ ] `NOTES.md` with the prompt-version experiment log
- [ ] Threats to validity written and honest
- [ ] 30-second demo GIF
- [ ] Non-goals stated explicitly
- [ ] Commit history shows phased development, not one dump
- [ ] No API keys anywhere in the repo or its history (`git log -p | grep -i sk-`)
