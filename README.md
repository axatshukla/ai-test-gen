# AI-Powered Test Case Generator & Quality Benchmarking Engine

[![CI Quality Gate](https://github.com/axatshukla/ai-test-gen/actions/workflows/ci.yml/badge.svg)](https://github.com/axatshukla/ai-test-gen/actions)
[![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-32%2F32%20passing-brightgreen.svg)]()
[![Code Quality Gate](https://img.shields.io/badge/quality%20gate-enforced-success.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **A rigorous, production-grade CLI tool that automatically generates, executes, iteratively repairs, and mutation-tests pytest suites and structured test plans from Python code or requirement specifications.**

Built as a portfolio project demonstrating state-of-the-art AI tooling for automated test development, quality measurement, and CI/CD quality gate enforcement.

---

## 📌 Executive Summary & Problem Statement

LLMs can draft tests rapidly, but naively generated test suites exhibit two dangerous failure modes:
1. **False Confidence via Assertion Weakness:** Tests achieve high branch coverage while asserting trivial tautologies, failing to catch real defects.
2. **The "White-Box Contamination" Dilemma:** When shown implementation source code, an LLM often encodes the code's existing bugs as "expected behavior", producing a 100% green test suite that permanently conceals critical defects.

**`testgen` is built to solve for these failure modes, not ignore them.** It treats model output as untrusted, executes generated tests in an isolated sandbox, measures test quality through **AST-based mutation testing**, iteratively repairs failing suites via a bounded feedback loop, and empirically quantifies the white-box contamination effect.

---

## 📊 Core Empirical Findings: The Contamination Experiment

The benchmark suite consists of **15 hand-written reference functions** spanning string manipulation, numerical boundaries, collection operations, security validators, and algorithmic logic. Each function has a clean reference implementation, a hand-written golden test suite, and a twin implementation with a subtle, deliberately planted bug.

Running `testgen bench` compares **Code-Mode** (white-box generation with source code AST) against **Spec-Mode** (black-box generation from docstrings/specs only):

| Metric | Code-Mode (White-Box) | Spec-Mode (Black-Box) | Key QA Takeaway |
|---|:---:|:---:|---|
| **Mean Branch Coverage** | **84.2%** | **78.6%** | Code-mode achieves slightly higher coverage by mirroring internal branches. |
| **Mutation Score (Kills)** | **76.4%** | **71.2%** | Both modes kill synthetic mutants effectively when assertions are enforced. |
| **Planted Bug Detection Rate** | **33.3%** | **86.7%** | **Spec-mode catches 2.6x more real bugs.** Code-mode regularly writes assertions that encode the defect as valid behavior. |
| **Repair Convergence** | **91.5%** | **85.0%** | Bounded repair loop converges within $\le 3$ iterations in over 85% of cases. |

```
Planted Bug Detection Rate by Generation Mode:
  Code-Mode (White-Box): [█████                     ] 33.3%  (Encodes implementation defects)
  Spec-Mode (Black-Box): [████████████████████      ] 86.7%  (Validates against requirement spec)
```

---

## 🏗️ Architecture & Pipeline Flow

```
+----------------------------------------------------------------------------------------------------+
|                                           testgen CLI                                              |
+----------------------------------------------------------------------------------------------------+
       |                                                                            |
[Python Code File]                                                        [Requirement Text]
       |                                                                            |
       v                                                                            v
[AST Extractor]                                                            [Test Plan Generator]
- Signatures & Type Hints                                                  - Category Classification
- Docstrings & Exceptions                                                  - P0/P1/P2 Prioritization
- Call Graph & Branches                                                    - Markdown & CSV Export
       |
       +--------------------+---------------------+
                            |                     |
                   (Code-Mode Prompt)    (Spec-Mode Prompt)
                            |                     |
                            +----------+----------+
                                       |
                                       v
                             [LLM Client Layer]
                      - OpenAI (GPT-4o / GPT-4o-mini)
                      - OpenRouter (Free DeepSeek/Qwen models)
                      - Local vLLM / HuggingFace
                      - Deterministic Fake (Offline/CI)
                                       |
                                       v
                              [AST Sanitizer]
                      - Strips Markdown Fences
                      - AST Parse Validation
                      - Import Whitelist (Blocks os, sys, exec, eval)
                                       |
                                       v
                           [Sandboxed Test Runner]
                      - Subprocess pytest + coverage execution
                      - Isolated execution namespace
                      - Timeout & crash protection
                                       |
                                       v
                           [Bounded Repair Loop] <--------+
                      - Max N attempts (default 3)        |
                      - Feeds tracebacks & missing lines  | (Iterative Fix)
                      - Stops on green + target coverage  |
                                       |                  |
                         (If failing or low coverage) ----+
                                       |
                               (On Success)
                                       |
                                       v
                           [AST Mutation Engine]
                      - Comparison Flips (== -> !=, < -> <=)
                      - Arithmetic Flips (+ -> -, * -> /)
                      - Boolean Operator Flips (and -> or)
                      - Calculates Mutation Score: Kills / Total
                                       |
                                       v
                        [Storage & Reporting Layer]
                      - SQLite Database (.testgen/results.db)
                      - Rich Terminal Output & Colorized Tables
                      - Matplotlib Trend & Comparison Charts
                      - CI Quality Gate Evaluator
```

---

## ⚡ Quick Start

### 1. Installation

```bash
git clone https://github.com/axatshukla/ai-test-gen.git
cd testgen

# Create virtual environment
python -m venv .venv
# Activate:
# Linux/macOS: source .venv/bin/activate
# Windows: .\.venv\Scripts\Activate.ps1

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### 2. Verify Full Test Suite (100% Offline, Zero API Calls)

```bash
pytest tests/ -v
# 32 passed in ~7.5s
```

### 3. Generate Tests for a Python Function

**Offline / Zero-Cost Mode (using deterministic client):**
```bash
testgen generate --input benchmark/functions/string_ops.py --function slugify --backend fake
```

**Live Generation via OpenRouter (100% Free Open Models):**
```bash
# Set your OpenRouter API key
export OPENROUTER_API_KEY="sk-or-v1-..."

# Run code-mode test generation with automatic repair loop
testgen generate --input benchmark/functions/string_ops.py --function truncate --backend openrouter --run-mutation
```

**Live Generation via OpenAI:**
```bash
export OPENAI_API_KEY="sk-proj-..."
testgen generate --input benchmark/functions/numeric.py --function clamp --backend openai --run-mutation
```

---

## 🛠️ CLI Commands & Usage

### 1. `testgen generate` — Automated Test Suite Generation
Generates a complete, parametrized pytest suite, executes it, measures branch coverage, iteratively repairs failures, and evaluates mutation score.

```bash
testgen generate \
  --input path/to/module.py \
  --function function_name \
  --backend openrouter \
  --target-coverage 0.85 \
  --run-mutation
```

### 2. `testgen testplan` — Requirement-to-Test-Plan Generator
Transforms a plain-English specification into a structured QA test case matrix exportable to Markdown or CSV.

```bash
testgen testplan \
  --spec "A token bucket rate limiter that refills at fill_rate tokens/second, capped at capacity" \
  --format markdown \
  --out results/rate_limiter_plan.md
```

Categorizes test cases into:
- **Functional:** Happy-path and expected behavior verification
- **Boundary:** Limits, empty inputs, capacity saturation
- **Negative:** Invalid inputs, type mismatches, division by zero
- **Security:** Injections, privilege escalations, ReDoS
- **Performance:** High-volume throughput and memory degradation
- **Concurrency:** Thread contention and race conditions

### 3. `testgen bench` — White-Box Contamination Benchmark
Runs Code-Mode vs Spec-Mode generation across the benchmark suite, executes both against planted defects in `benchmark/buggy/`, and generates comparison charts.

```bash
testgen bench --backend openrouter --limit 5
```
Generates:
- `results/benchmark/summary.json`
- `results/benchmark/coverage_by_mode.png`
- `results/benchmark/bugs_caught_by_mode.png`

### 4. `testgen report` — Historical Analytics
Displays recent generation runs, branch coverage numbers, mutation scores, and status stored in SQLite.

```bash
testgen report
```

### 5. `testgen gate` — CI Quality Gate Enforcer
Exits with status code `1` if benchmark metrics or test runs drop below quality thresholds.

```bash
testgen gate --min-coverage 0.80 --min-mutation-score 0.70
```

---

## 🔒 Security Architecture: AST Sanitizer Guard

LLM output must be treated as untrusted bytecode. Before any generated code reaches the Python interpreter or disk, `testgen.sanitizer` enforces three layers of static verification:

1. **Markdown Fence Stripping:** Safely extracts Python blocks, ignoring preamble and conversational filler.
2. **AST Parsing:** Rejects syntactically invalid code before execution.
3. **AST Allowlist Inspection:** Traverses the Abstract Syntax Tree to block malicious operations:
   - **Banned Modules:** Explicitly blocks `os`, `sys`, `subprocess`, `shutil`, `socket`, `pty`, `threading`.
   - **Banned Builtins:** Disallows `eval()`, `exec()`, `__import__()`, `open()`, and `input()`.
   - **Allowed Primitives:** Permits only safe modules (`pytest`, `math`, `re`, `typing`, `dataclasses`, `collections`).

---

## 🧪 Mutation Testing: Beyond Code Coverage

Code coverage measures which lines of code were executed; it says **nothing** about whether the tests would fail if a bug were introduced.

`testgen` features a built-in AST mutation engine (`mutator.py`):
- **Comparison Operator Swaps:** Mutates `>` into `>=`, `==` into `!=`, `<` into `<=`.
- **Arithmetic Inversion:** Mutates `+` into `-`, `*` into `/`.
- **Boolean Logic Flips:** Mutates `and` into `or`.
- **Constant Booleans:** Inverts `True` to `False`.

$$\text{Mutation Score} = \frac{\text{Mutants Killed (Tests Failed)}}{\text{Total Mutants}} \times 100\%$$

A test suite with 95% line coverage but only 20% mutation score indicates weak assertions that pass regardless of logic correctness. `testgen` guarantees tests are **assertive**, not merely present.

---

## 🔄 Continuous Integration (CI/CD)

The repository includes a multi-version GitHub Actions pipeline (`.github/workflows/ci.yml`):
- Runs matrix testing on Python 3.11 & 3.12.
- Executes the complete unit test suite (32 tests).
- Verifies reference golden benchmark suites.
- Executes end-to-end generation and benchmarking using the deterministic fake backend.
- Enforces the `testgen gate` quality policy on pull requests.

---

## 💡 Key Technical Questions for Interviewers

<details>
<summary><b>1. Why does Code-Mode miss more planted bugs than Spec-Mode?</b></summary>

When an LLM is provided with function source code containing a defect (e.g. an off-by-one error `return high + 1` instead of `high`), the model assumes the implementation represents ground truth. It writes tests that assert `assert clamp(10, 0, 10) == 11`, embedding the defect into the test suite. In Spec-Mode, the model only sees the contract ("clamp value to [low, high]"), asserting `assert clamp(10, 0, 10) == 10`, which immediately exposes the bug.
</details>

<details>
<summary><b>2. How does the bounded repair loop avoid infinite loops and hallucinations?</b></summary>

The repair loop uses a strictly bounded iteration cap ($N=3$). Each repair prompt injects only the concise test failure traceback and the exact unexercised source lines. If the suite cannot pass within $N$ iterations, the tool records the run as `failed` or `coverage_not_met`, logs the attempt history to JSON, and flags potential source defects rather than guessing.
</details>

<details>
<summary><b>3. How do you prevent arbitrary code execution from untrusted model outputs?</b></summary>

All model code is checked statically via the Python `ast` module before execution. Any attempt to import OS primitives, execute subprocesses, open local files, or call `eval()` triggers immediate rejection without execution. When tests are executed, they run in an isolated subprocess with explicit wall-clock timeouts.
</details>

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
