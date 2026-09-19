# Prompt Experiment Log

Dated record of every prompt change and its measured impact.
This file is the evidence for "I iterated on the prompt" in an interview.

---

## 2026-09-20 · Baseline setup

- **Prompt version:** CODE_MODE_V3, SPEC_MODE_V3
- **Key rules added vs naive baseline (V1):**
  - Import allowlist enforced in system message
  - Naming convention: `test_<function>_<condition>_<expected_outcome>`
  - Category coverage: happy path, boundary, invalid types, edge cases, error paths
  - **Ambiguity rule:** `xfail` instead of guessing
- **Starting metrics:** TBD (run benchmark to populate)

---

## Template

```
YYYY-MM-DD · vN ? vN+1: <what changed>
  syntactic validity: X% ? Y%
  mutation score (code mode): X% ? Y%
  spec-mode false-failure rate: X% ? Y%
  planted-bug detection: X% ? Y%
  notes: <what you observed and why you made this change>
```
