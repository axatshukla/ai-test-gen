# Product Requirements Document (PRD)
## AI-Powered Test Case Generator

**Version:** 1.0
**Owner:** You (solo project — portfolio piece for NVIDIA Software QA & Testing Dev Internship)
**Status:** Draft for build

---

## 1. Summary

A command-line tool that takes either (a) a Python function/module or (b) a plain-English requirement description, and uses an LLM to generate pytest test suites or structured test plans automatically. The tool doesn't just generate tests — it executes them, measures their real effectiveness (coverage + mutation testing), iteratively repairs failing/weak tests, and reports quantified quality metrics.

This maps directly to the internship JD line: *"AI development tools for test plans creation, test cases development and automation."*

## 2. Problem Statement

Writing comprehensive test suites is slow and inconsistent — engineers under deadline pressure write happy-path tests and skip edge cases, error paths, and boundary conditions. LLMs can draft tests fast, but naively generated tests have two known failure modes that make them unsafe to trust blindly:

1. **They look plausible but don't actually test anything meaningful** (weak assertions, only happy-path coverage).
2. **When shown the implementation, they encode the implementation's bugs as "expected behavior"** — a green test suite that hides real defects.

A QA-oriented AI tool has to solve *for* these failure modes, not ignore them. That's the actual problem this project addresses — not "can an LLM write a test" (yes, trivially) but "how do you know the generated tests are trustworthy."

## 3. Goals

- **G1:** Given a Python function, auto-generate a pytest suite with parametrized happy-path, boundary, invalid-input, and error-path cases.
- **G2:** Given a requirement description, auto-generate a structured test plan (test case table: ID, category, precondition, steps, expected result, priority) exportable as CSV.
- **G3:** Automatically execute generated tests, measure branch coverage, and iteratively repair failing or low-coverage suites (bounded retry loop).
- **G4:** Quantify test *quality*, not just existence — via mutation testing (does the suite catch injected bugs?).
- **G5:** Empirically demonstrate and document the "white-box contamination" problem (generating from source vs. from spec) with real numbers on a benchmark set.
- **G6:** Support at least two LLM backends (a hosted API and a locally-served open model) behind one interface.
- **G7:** Ship with a benchmark suite, CI pipeline, and a README that leads with real metrics — so the project is self-evidently rigorous to an interviewer skimming GitHub.

## 4. Non-Goals

- Not building a production CI/CD gate that auto-merges AI-written tests with no human review (the project's own findings argue against this — see Section 9).
- Not supporting arbitrary languages — Python only, to keep scope achievable in the available time.
- Not building a hosted web product, team accounts, auth, or billing. A local CLI (+ optional single-user local API/UI, see TRD) is sufficient to demonstrate the skill.
- Not fine-tuning a model. Prompt engineering + off-the-shelf models only.
- Not achieving 100% mutation score or coverage — the goal is to *measure and report* quality honestly, not to inflate a number.

## 5. Target User / Use Case

Primary "user" is you, in an interview, and secondarily an engineer who wants to bootstrap test coverage on a legacy module that has none. Design decisions should optimize for **explainability and demonstrable rigor** over polish — an interviewer will read the code and the metrics, not click through a UI.

## 6. User Stories

- As a developer, I want to point the tool at a function and get a runnable pytest file, so I don't start test-writing from a blank page.
- As a developer, I want the tool to tell me when it *can't* infer expected behavior (ambiguous spec) instead of guessing, so I don't get false confidence from a passing test that asserts the wrong thing.
- As a QA lead, I want a test plan generated from a requirement description in a format I can import into a test management tool, so I can use this for planning, not just unit tests.
- As a reviewer of this project, I want a benchmark report showing coverage, mutation score, and bug-catch rate, so I can evaluate whether the tool actually works rather than taking a demo's word for it.

## 7. Functional Requirements

### FR1 — Code-mode test generation
- Input: path to a `.py` file (and optionally a specific function name).
- Extract function signature, type hints, docstring, source, and raised exceptions via `ast`.
- Generate a pytest file covering: happy path, boundary values, invalid types/None, edge cases, and one test per raised/documented exception.
- Ambiguous/underspecified behavior must be marked `xfail` with a reason, never silently asserted.

### FR2 — Spec-mode test generation
- Input: free-text requirement description (no source code shown to the model).
- Same output contract as FR1, generated purely from the description.

### FR3 — Test plan generation
- Input: free-text requirement description.
- Output: structured test case table (ID, category, precondition, steps, expected result, priority) with categories: functional, boundary, negative, security, performance, concurrency.
- Exportable as CSV and Markdown.

### FR4 — Execution & repair loop
- Run generated tests via `pytest` + `coverage` in a subprocess with a timeout.
- If tests fail or branch coverage is below target, feed back failure tracebacks and uncovered source lines (not line numbers) to the model for a bounded number of repair attempts (default 3).
- Distinguish "test is wrong" (repair the test) from "suspected source bug" (report, don't silently patch).

### FR5 — Mutation-based quality scoring
- Apply a mutation operator set (comparison flips, arithmetic op flips, boolean op flips, return-value nulling) to the source under test.
- Run the generated suite against each mutant; report mutation score = mutants killed / mutants total.

### FR6 — Benchmark & contamination experiment
- Maintain a benchmark of 15–20 hand-written functions, each with a hand-written "golden" test suite and a deliberately buggy variant.
- Run both code-mode and spec-mode generation against the benchmark; report coverage, mutation score, and planted-bug catch rate for each mode side by side.

### FR7 — Pluggable LLM backend
- Support OpenAI API, Hugging Face Inference API, and a locally served OpenAI-compatible endpoint (vLLM), selected via CLI flag/config — no code changes required to switch.

### FR8 — CLI
- `generate`, `testplan`, `benchmark`, `report` subcommands (see TRD/API spec for exact interface).

### FR9 — Safety sanitization
- All model output is treated as untrusted: syntax-checked, import-whitelisted, and executed with a timeout before being trusted or saved as final output.

## 8. Success Metrics

These are the numbers the README and the interview conversation lead with:

| Metric | Target | Why it matters |
|---|---|---|
| Branch coverage on benchmark (mean) | ≥ 80% | Basic completeness signal |
| Mutation score, generated vs. hand-written baseline | Report both, gap < 20 pts | Shows tests are meaningfully assertive, not just present |
| Planted-bug catch rate, spec-mode vs. code-mode | Spec-mode measurably higher | The project's core empirical finding |
| Repair loop convergence | ≥ 80% of functions pass + hit coverage target within 3 iterations | Shows the loop is useful, not decorative |
| Syntactically valid output rate | ≥ 95% | Sanitizer/prompt quality signal |

## 9. Risks & Key Findings to Report Honestly

- **Risk:** LLM-generated tests that pass do not imply correct code — they may encode existing bugs. **Mitigation:** the whole white-box/black-box experiment exists to measure and expose this, and the ambiguity rule (Section 7, FR1) prevents silent guessing.
- **Risk:** Non-determinism across runs. **Mitigation:** pin model version + temperature (0.2–0.3), log both in output headers, gate on measured score not textual equality.
- **Risk:** Cost/rate limits on hosted APIs during heavy benchmark runs. **Mitigation:** local vLLM backend as fallback; cache prompts/responses during development.
- **Honest conclusion to state up front, not hide:** this tool is a draft-generation and coverage-bootstrapping aid for human review — not an unsupervised test-authoring system. That's a QA-appropriate conclusion, not a weakness.

## 10. Milestones

| Phase | Scope | Ties to |
|---|---|---|
| M1 | FR1, FR7 (single backend), FR9 | v1 MVP |
| M2 | FR4 | v2 |
| M3 | FR5, FR6 | v3 |
| M4 | FR2, FR3, FR7 (all backends), FR8 polish, CI | v4 |

See `04_IMPLEMENTATION_GUIDE.md` for the hour-by-hour breakdown.

## 11. Out-of-Scope / Explicitly Skipped for This PRD

- Multi-language support, hosted multi-user product, auth/billing, fine-tuning — omitted as unnecessary for a portfolio project scoped to a QA internship application (see Non-Goals).
