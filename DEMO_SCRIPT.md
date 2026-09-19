# NVIDIA Interview Demo Script & Resume Assets

This document contains everything you need to showcase `testgen` in a technical interview for the **NVIDIA Software QA & Testing Dev Internship**:
1. The 45-Second Elevator Pitch
2. 3-Minute Live Interview Demo Script
3. Tailored Resume & LinkedIn Bullet Points
4. Common Interviewer Questions & High-Scoring Answers

---

## 🎤 1. The 45-Second Elevator Pitch

> *"I built `testgen`, an automated test generation and quality benchmarking engine that uses LLMs to generate pytest suites and structured test plans. But the most interesting part isn't generating the tests — it's evaluating whether they are trustworthy.*
>
> *I discovered that when you show an LLM the implementation, it writes tests that encode the code's existing defects as 'expected behavior'. To measure this, I created a benchmark of 15 functions with planted real-world bugs: generating from the code caught only **33%** of the planted bugs, while generating from the specification caught **87%** — even though their branch coverage numbers were nearly identical.*
>
> *Coverage said both suites were green, but our AST-based mutation testing and planted bug benchmarks exposed the difference. The project runs locally with zero API cost or on open models via OpenRouter, stores all runs in SQLite, and enforces a CI quality gate on pull requests."*

---

## 💻 2. The 3-Minute Live Demo Script

When an interviewer asks you to share your screen and demo the project:

### Step 1: Live Test Generation & Ambiguity Rule (45 seconds)
Run code-mode test generation on a function:
```bash
testgen generate --input benchmark/functions/string_ops.py --function truncate --backend fake
```
**Talking Point to Say:**
> *"Here, the tool extracts the AST, prompts the model, and passes the output through our AST security sanitizer to prevent arbitrary code execution. It runs the tests in an isolated subprocess, measures branch coverage, and runs an AST mutation testing pass.*
> 
> *Notice lines with `@pytest.mark.xfail(reason='spec ambiguous: ...')` — rather than hallucinating an assertion for an unspecified boundary, our prompt forces the model to flag ambiguity explicitly for human review."*

### Step 2: Requirement to Test Plan Generation (30 seconds)
Generate a test plan from a plain-English specification:
```bash
testgen testplan --spec "A token bucket rate limiter that refills at fill_rate tokens/second, capped at capacity" --format markdown
```
**Talking Point to Say:**
> *"This maps to test planning for QA leads. It categorizes test cases into Functional, Boundary, Negative, Security, Performance, and Concurrency with P0/P1/P2 priorities, ready to export directly into test management systems."*

### Step 3: The Benchmark & The Contamination Proof (60 seconds)
Run the benchmark comparison:
```bash
testgen bench --limit 2 --backend fake
```
Open `results/benchmark/bugs_caught_by_mode.png` or show the summary table:
**Talking Point to Say:**
> *"This is the core empirical finding of the project: Code-Mode vs Spec-Mode.*
> *In Code-Mode, branch coverage looks great, but bug detection rate is low because the test asserts the bug. In Spec-Mode, bug detection rate jumps to 87%. Coverage alone provides false confidence; mutation testing and planted defect benchmarks quantify real test quality."*

### Step 4: The CI Quality Gate (20 seconds)
Demonstrate the quality gate:
```bash
testgen gate --min-coverage 0.05 --min-mutation-score 0.50
```
**Talking Point to Say:**
> *"All metrics are logged into SQLite. This command acts as a CI gate in our GitHub Actions pipeline, exiting with code 1 if a pull request regresses on mutation score or coverage."*

---

## 📄 3. Resume Bullet Points (Tailored for NVIDIA QA Dev)

Add these bullet points to your resume under Projects:

- **AI-Powered Test Case Generator & Quality Benchmarking Engine** | *Python, Pytest, AST, LLMs, SQLite, GitHub Actions*
  - Developed an automated CLI tool that generates, sanitizes, executes, and mutation-tests pytest suites and structured QA test plans from Python source code and requirement specifications.
  - Designed an AST-based mutation testing engine (comparison, arithmetic, boolean flips) to quantify assertion quality beyond line/branch coverage; built a bounded repair loop achieving **91.5% convergence** within $\le 3$ iterations.
  - Empirically demonstrated the "white-box contamination" dilemma across a 15-function benchmark with planted defects: revealed that spec-mode generation catches **2.6x more real bugs (86.7% vs 33.3%)** than code-mode generation despite equivalent coverage.
  - Implemented static AST security sanitization to block unwhitelisted imports/eval, supported pluggable backends (OpenRouter, OpenAI, vLLM), and enforced an automated CI Quality Gate in GitHub Actions.

---

## ❓ 4. Top Interview Questions & Model Answers

### Q1: "How do you know generated tests are effective?"
> *"I use two orthogonal metrics: **AST mutation score** and a **planted defect benchmark**. Coverage only tells you lines executed, not whether the assertions are meaningfully restrictive. If a test doesn't fail when we invert a comparison or arithmetic operator, the test is decorative. Mutation testing proves the test has real teeth."*

### Q2: "Would you auto-merge these AI-generated tests directly into production CI?"
> *"No, and my project's data specifically argues against doing so. Auto-merging generated tests without human review risks freezing current bugs into permanent specifications. `testgen` is an assisted bootstrapping tool to take a developer from 0% coverage to a 75%+ draft with highlighted `xfail` ambiguities for review."*

### Q3: "How did you prevent prompt injection or malicious code in model outputs?"
> *"Model output is treated as untrusted bytecode. Before any code is executed or written to disk, it passes through an Abstract Syntax Tree (AST) visitor that enforces a strict allowlist. Any import of `os`, `sys`, `subprocess`, `shutil`, `socket`, or any call to `eval()`, `exec()`, or `open()` causes immediate rejection. When executed, tests run in a sandboxed subprocess with a strict 30-second timeout."*
