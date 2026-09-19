# Interview Brief — `testgen` at NVIDIA (Software QA & Testing Dev Intern)

---

## 1. The 45-second pitch

> "I built a tool that generates pytest suites from Python functions using an LLM — but
> the interesting part isn't the generation, it's the evaluation. When you show the model
> the implementation, it writes tests that assert whatever the code currently does,
> including its bugs. So I built a benchmark of 20 functions with planted defects and
> measured it: generating from the implementation caught 40% of planted bugs, generating
> from only the docstring caught 73% — while the coverage numbers were nearly identical.
> Coverage said both suites were fine. Only mutation testing and the planted-bug
> benchmark showed the difference. The tool runs on a local 7B model through vLLM, stores
> every run in SQLite, and has a CI gate that fails on mutation-score regression."

Then stop. Let them pick the thread.

## 2. Mapping to the job description

| JD phrase | Your evidence |
|---|---|
| "AI development tools for test plans creation" | Plan mode: requirement text → categorized test-case table, CSV export |
| "test cases development" | Code/spec mode: function → executable pytest suite |
| "automation" | CLI, CI gate, GitHub Actions workflow, exit codes for pipeline use |
| Test methodology | Branch coverage vs mutation score; equivalent mutants; boundary/negative/error-path taxonomy |
| Quality mindset | Threats-to-validity section; refused to auto-merge generated tests |
| GPU/infra awareness | vLLM self-hosted inference, continuous batching throughput measurement |

## 3. Demo script (3 minutes)

1. `testgen generate benchmark/functions/binary_search.py --mode spec` — live, one
   function, show the generated file and the results table. (15s with a warm local model.)
2. Open the generated file, point at the provenance header and one `xfail` marker:
   *"the model flagged that the spec doesn't define behavior for an empty array instead of
   inventing an answer."*
3. `testgen bench --planted-bugs --modes code,spec` on cached results — show the chart.
   **This is the moment.** Say the coverage-identical / detection-divergent line.
4. `testgen gate --latest --min-mutation-score 0.65` — show it exiting 1 on a regression.

Have all of it cached and pre-warmed. A live API call that hangs kills the demo.

## 4. Questions they will ask

**"How do you know the generated tests are any good?"**
Mutation score against my hand-written baseline, plus planted-bug detection rate. Coverage
alone is insufficient — a test that calls a function and asserts nothing gets 100%
coverage and kills zero mutants.

**"What if the model asserts buggy behavior as correct?"**
That's the central failure mode, and it's why the project exists. Three mitigations: spec
mode so the model never sees the implementation; an ambiguity rule that forces `xfail`
instead of a guessed assertion; and a benchmark that quantifies the residual risk rather
than assuming it away.

**"Would you let this run unsupervised in CI?"**
No. Generated tests are a reviewed draft. Auto-merging them freezes current behavior as the
specification permanently. The good use case is bootstrapping coverage on a legacy module
that has none — where the alternative is zero tests, not good tests.

**"LLMs are non-deterministic. How is this CI-safe?"**
Temperature 0.2, pinned model and prompt version, response cache, and — most importantly —
the gate evaluates *measured metrics*, never text equality. Generation happens offline and
produces a reviewed artifact; CI validates the artifact.

**"What broke most often?"**
Be specific, with numbers from your failure taxonomy: hallucinated helper imports (~4% of
generations), floats compared with `==`, wrong exception type on error-path tests, tests
written for private helpers. Each one drove a prompt constraint. Show `NOTES.md`.

**"Why write your own mutation engine instead of using mutmut?"**
Control and speed — I needed per-target mutant caps and programmatic kill records in
SQLite. I cross-validated against mutmut on three functions and reported the agreement, so
the numbers aren't self-flattering.

**"How would you scale this to a large codebase?"**
Batch generation through vLLM's continuous batching (I measured the speedup), prioritize
targets by cyclomatic complexity × change frequency × current coverage gap, cache by
function source hash so unchanged code is never regenerated, and shard mutation analysis
since it's embarrassingly parallel.

**"What would you do differently?"**
Property-based testing — have the LLM write Hypothesis properties and let Hypothesis
generate inputs. That sidesteps the whole "model invents expected values" problem, because
properties are invariants rather than specific assertions. It's the first thing I'd build
next.

**"What's the weakest part?"**
The failure classifier distinguishing a broken test from a real source defect is a
heuristic and it's wrong maybe a fifth of the time. It needs either a stronger signal or a
human in the loop, and I chose to report it as a limitation rather than hide it.

## 5. Things to avoid saying

- "It works really well" — give a number instead.
- "The AI handles that" — describe the mechanism.
- Overclaiming n=20 as statistical significance. Say "measured on 20 functions, three
  seeds, error bars in the chart."
- Pretending the planted bugs are realistic. They aren't fully, and saying so first is
  stronger than being caught.
- Describing it as replacing testers. Frame as first-draft acceleration.

## 6. README opening template

```markdown
# testgen — AI test generation with a quality gate

Generates pytest suites from Python functions, then measures whether those tests
actually catch bugs.

**Results** (20-function benchmark, 3 seeds, Qwen2.5-Coder-7B local):

|                        | Code mode | Spec mode | Hand-written |
|------------------------|-----------|-----------|--------------|
| Branch coverage        | 0.88      | 0.83      | 0.92         |
| Mutation score         | 0.63      | 0.71      | 0.84         |
| Planted bugs caught    | 40%       | 73%       | 100%         |
| False failures         | 2%        | 15%       | 0%           |

![bugs caught by mode](results/charts/bugs_caught_by_mode.png)

**The finding:** showing the model the implementation produces higher coverage and
worse defect detection. It writes assertions that encode existing behavior — bugs
included. Coverage cannot see this; mutation testing can.

> Generated tests are a reviewed draft, never an auto-merge. See Limitations.
```

## 7. Keep a `NOTES.md`

A dated log of prompt versions and what each change did to the metrics:

```
2026-09-21 · v1 → v2: added import allowlist + naming convention to prompt.
  syntactic validity 0.81 → 0.96. Hallucinated `from utils import helper` was 60%
  of rejections.

2026-09-22 · v2 → v3: added ambiguity rule (xfail for unspecified behavior).
  spec-mode false-failure rate 0.31 → 0.15, planted-bug detection unchanged (0.71 → 0.73).
  Best change in the project.
```

When they ask how you approached prompt engineering, open this file. An experiment log
beats any description of your process.
