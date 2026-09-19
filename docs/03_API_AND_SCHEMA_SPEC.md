# Backend Schema & API Specification
## AI-Powered Test Case Generator

**Companion to:** `01_PRD.md`, `02_TRD.md`
**Scope note:** The tool is CLI-first (Section 1). Sections 2–4 (REST API + database) are an **optional Phase 4 stretch layer** for browsing past runs through a small local dashboard — build it only if time allows after the core pipeline (PRD Phases M1–M3) works. Skip it entirely and the project is still complete; a CLI tool is a legitimate deliverable for this JD.

---

## 1. CLI Interface (the real "API" of this project)

### `generate` — code-mode or spec-mode test generation

```
ai-test-gen generate
  --input PATH               .py file (code mode) — mutually exclusive with --spec
  --spec TEXT                requirement description (spec mode) — mutually exclusive with --input
  --function NAME             optional: only generate for this function
  --backend {openai,hf,vllm} default: openai
  --model NAME                e.g. gpt-4o-mini, Qwen2.5-Coder-7B-Instruct
  --temperature FLOAT         default: 0.2
  --target-coverage FLOAT     default: 0.80
  --max-iters INT             default: 3
  --out PATH                  default: tests/test_<module>.py
  --report PATH               default: results/<run_id>/report.json

Exit codes:
  0  success — tests generated, passed, coverage target met
  1  generation failed (LLM error after retries)
  2  sanitization failed on all attempts
  3  tests ran but did not meet coverage target within max-iters
  4  invalid input (bad file path, syntax error in target file, etc.)
```

**Example:**
```
ai-test-gen generate --input src/utils/string_ops.py --function slugify \
  --backend vllm --model Qwen/Qwen2.5-Coder-7B-Instruct
```

### `testplan` — structured test plan from a requirement

```
ai-test-gen testplan
  --spec TEXT | --spec-file PATH
  --backend {openai,hf,vllm}
  --model NAME
  --format {csv,markdown}     default: markdown
  --out PATH                  default: results/testplan.<ext>
```

Output row schema (see §2.3 for the formal shape — used identically whether written to CSV, Markdown, or the optional DB):
`id, category, precondition, steps, expected_result, priority`

### `benchmark` — run the full benchmark + contamination experiment

```
ai-test-gen benchmark
  --suite-dir PATH             default: benchmark/
  --backend {openai,hf,vllm}
  --model NAME
  --modes {code,spec,both}     default: both
  --out-dir PATH               default: results/benchmark/<timestamp>/
```
Produces `summary.md`, `summary.json`, and two PNG charts (coverage-by-mode, bug-catch-rate-by-mode).

### `report` — render a human-readable report from a prior run's JSON

```
ai-test-gen report --run-id ID   # or --json-path PATH
```

---

## 2. Optional REST API (Phase 4 stretch — FastAPI)

Only build this if you want a small local dashboard on top of the CLI's outputs. It wraps the same underlying pipeline functions — it is not a second implementation.

### 2.1 Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/runs` | Start a generation run (code or spec mode). Body: see §2.2. Returns `run_id` immediately; processing happens async. |
| GET | `/api/runs/{run_id}` | Poll run status + result summary once complete. |
| GET | `/api/runs/{run_id}/report` | Full `report.json` for the run. |
| GET | `/api/runs/{run_id}/test-file` | Download the generated `.py` test file. |
| POST | `/api/testplans` | Generate a test plan from a spec string. Returns rows inline (synchronous — test plan generation has no execution/repair loop, so it's fast). |
| GET | `/api/testplans/{testplan_id}` | Retrieve a previously generated test plan. |
| POST | `/api/benchmarks` | Kick off a full benchmark run. Returns `benchmark_id`. |
| GET | `/api/benchmarks/{benchmark_id}` | Benchmark status + summary metrics once complete. |
| GET | `/api/functions` | List functions available in the loaded benchmark suite (for a UI dropdown). |

### 2.2 Request / Response Examples

**POST /api/runs**
```json
// Request
{
  "mode": "code",                 // "code" | "spec"
  "source_code": "def slugify(text: str) -> str:\n    ...",
  "spec_text": null,
  "function_name": "slugify",
  "backend": "openai",
  "model": "gpt-4o-mini",
  "temperature": 0.2,
  "target_coverage": 0.80,
  "max_iters": 3
}

// Response (202 Accepted)
{
  "run_id": "run_7f3a1c",
  "status": "queued",
  "created_at": "2026-09-19T10:15:00Z"
}
```

**GET /api/runs/{run_id}**
```json
{
  "run_id": "run_7f3a1c",
  "status": "completed",           // queued | running | completed | failed
  "attempts": 2,
  "final_result": {
    "passed": 11,
    "failed": 0,
    "xfailed": 1,
    "branch_coverage": 0.86,
    "mutation_score": 0.74,
    "suspected_source_bugs": []
  },
  "model": "gpt-4o-mini",
  "prompt_version": "CODE_MODE_V3",
  "temperature": 0.2,
  "created_at": "2026-09-19T10:15:00Z",
  "completed_at": "2026-09-19T10:15:42Z"
}
```

**POST /api/testplans**
```json
// Request
{
  "spec_text": "The login endpoint accepts email and password, locks the account for 15 minutes after 5 failed attempts, and returns a JWT valid for 24 hours.",
  "backend": "openai",
  "model": "gpt-4o-mini"
}

// Response (200 OK)
{
  "testplan_id": "tp_29ab",
  "rows": [
    {
      "id": "TC-001",
      "category": "functional",
      "precondition": "valid registered user",
      "steps": "POST /login with valid email + password",
      "expected_result": "200 response with JWT",
      "priority": "P0"
    },
    {
      "id": "TC-007",
      "category": "security",
      "precondition": "4 prior failed attempts",
      "steps": "Submit a 5th incorrect password",
      "expected_result": "Account locked; 423 response",
      "priority": "P0"
    }
  ]
}
```

### 2.3 Shared Data Contracts (used by both CLI JSON output and the API)

```json
// FunctionSpec (as serialized)
{
  "name": "slugify",
  "args": [["text", "str"]],
  "returns": "str",
  "docstring": "Convert text to a URL-safe slug.",
  "raises": ["ValueError"],
  "module_path": "src/utils/string_ops.py"
}

// TestPlanRow
{
  "id": "TC-001",
  "category": "functional | boundary | negative | security | performance | concurrency",
  "precondition": "string",
  "steps": "string",
  "expected_result": "string",
  "priority": "P0 | P1 | P2"
}

// RunReport
{
  "run_id": "string",
  "mode": "code | spec",
  "function": "FunctionSpec",
  "model": "string",
  "prompt_version": "string",
  "temperature": "number",
  "attempts": [
    {
      "attempt_number": 1,
      "passed": "int",
      "failed": "int",
      "xfailed": "int",
      "branch_coverage": "number",
      "uncovered_lines": [[42, "if x < 0: raise ValueError(...)"]],
      "failure_details": [{"test_name": "string", "traceback": "string (truncated)"}]
    }
  ],
  "mutation_score": "number",
  "suspected_source_bugs": ["string"],
  "final_status": "passed | coverage_not_met | failed"
}
```

### 2.4 Error Responses

Standard shape for all endpoints:
```json
{
  "error": {
    "code": "LLM_TIMEOUT | SANITIZATION_FAILED | INVALID_INPUT | RUN_NOT_FOUND | INTERNAL_ERROR",
    "message": "human-readable description",
    "run_id": "string | null"
  }
}
```
| HTTP status | code |
|---|---|
| 400 | `INVALID_INPUT` |
| 404 | `RUN_NOT_FOUND` |
| 422 | `SANITIZATION_FAILED` |
| 502 | `LLM_TIMEOUT` / upstream backend error |
| 500 | `INTERNAL_ERROR` |

---

## 3. Database Schema (only needed if building the optional API/dashboard)

SQLite is sufficient (single user, local, no concurrency concerns). Use `sqlite3` directly or `SQLModel`/`SQLAlchemy` if you want typed models.

```sql
CREATE TABLE functions (
    id              TEXT PRIMARY KEY,          -- e.g. "func_<hash>"
    name            TEXT NOT NULL,
    module_path     TEXT NOT NULL,
    source          TEXT NOT NULL,
    docstring       TEXT,
    args_json       TEXT NOT NULL,              -- serialized [[name, type], ...]
    returns         TEXT,
    raises_json     TEXT NOT NULL,              -- serialized ["ValueError", ...]
    created_at      TEXT NOT NULL
);

CREATE TABLE runs (
    id                  TEXT PRIMARY KEY,       -- run_id
    function_id         TEXT REFERENCES functions(id),
    mode                TEXT NOT NULL CHECK (mode IN ('code','spec')),
    backend             TEXT NOT NULL,
    model               TEXT NOT NULL,
    temperature         REAL NOT NULL,
    prompt_version      TEXT NOT NULL,
    target_coverage     REAL NOT NULL,
    max_iters           INTEGER NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed')),
    final_status        TEXT,                    -- passed | coverage_not_met | failed
    branch_coverage     REAL,
    mutation_score      REAL,
    created_at          TEXT NOT NULL,
    completed_at        TEXT
);

CREATE TABLE run_attempts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT REFERENCES runs(id),
    attempt_number      INTEGER NOT NULL,
    generated_code      TEXT NOT NULL,
    passed              INTEGER NOT NULL,
    failed              INTEGER NOT NULL,
    xfailed             INTEGER NOT NULL,
    branch_coverage     REAL NOT NULL,
    uncovered_lines_json TEXT,                   -- serialized [[line_no, text], ...]
    failure_details_json TEXT,                    -- serialized [{test_name, traceback}, ...]
    created_at          TEXT NOT NULL
);

CREATE TABLE suspected_source_bugs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT REFERENCES runs(id),
    description     TEXT NOT NULL,
    test_name       TEXT NOT NULL
);

CREATE TABLE testplans (
    id              TEXT PRIMARY KEY,           -- testplan_id
    spec_text       TEXT NOT NULL,
    backend         TEXT NOT NULL,
    model           TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE testplan_rows (
    id                  TEXT NOT NULL,           -- e.g. "TC-001"
    testplan_id         TEXT REFERENCES testplans(id),
    category            TEXT NOT NULL,
    precondition        TEXT,
    steps               TEXT NOT NULL,
    expected_result     TEXT NOT NULL,
    priority            TEXT NOT NULL CHECK (priority IN ('P0','P1','P2')),
    PRIMARY KEY (id, testplan_id)
);

CREATE TABLE benchmarks (
    id                  TEXT PRIMARY KEY,       -- benchmark_id
    modes               TEXT NOT NULL,           -- 'code' | 'spec' | 'both'
    backend             TEXT NOT NULL,
    model               TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed')),
    mean_coverage_code  REAL,
    mean_coverage_spec  REAL,
    mean_mutation_code  REAL,
    mean_mutation_spec  REAL,
    bugs_caught_code    INTEGER,
    bugs_caught_spec    INTEGER,
    bugs_total          INTEGER,
    created_at          TEXT NOT NULL,
    completed_at        TEXT
);

CREATE INDEX idx_runs_function_id ON runs(function_id);
CREATE INDEX idx_run_attempts_run_id ON run_attempts(run_id);
CREATE INDEX idx_testplan_rows_testplan_id ON testplan_rows(testplan_id);
```

**Notes:**
- Timestamps stored as ISO-8601 text (SQLite has no native datetime type) — keep it simple, avoid an ORM migration framework for a single-developer local tool.
- JSON columns (`args_json`, `uncovered_lines_json`, etc.) are a deliberate simplification over normalized child tables — appropriate for a local, single-writer tool; call this out as a known trade-off if asked ("I'd normalize these into child tables if this had to serve concurrent writers").
- No auth/user table — out of scope per PRD Non-Goals.

---

## 4. What Was Intentionally Skipped

Per your "skip if unnecessary" instruction:

- **No formal OpenAPI/Swagger YAML file** — the endpoint table and JSON examples above are sufficient for a project this size and are what you'd actually reference while building; generate the OpenAPI spec automatically from FastAPI (`/docs` is free) rather than hand-authoring one.
- **No message-queue/worker architecture** — "async" above just means FastAPI `BackgroundTasks` or a simple thread; a full Celery/Redis setup would be over-engineering for a single-user local tool and would read as such to an interviewer.
- **No auth, multi-tenancy, or rate-limiting schema** — not applicable to a local single-user CLI/dashboard.
- **No separate "supporting document"** beyond this file and the TRD — architecture, data flow, and component specs are already covered in `02_TRD.md` to avoid duplicating content across files.
