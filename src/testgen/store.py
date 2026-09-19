"""SQLite persistence layer for run history and metrics."""
from __future__ import annotations
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from testgen.models import RunReport


DDL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id                TEXT PRIMARY KEY,
    function          TEXT NOT NULL,
    module_path       TEXT NOT NULL,
    mode              TEXT NOT NULL CHECK (mode IN ('code','spec')),
    model             TEXT NOT NULL,
    prompt_version    TEXT NOT NULL,
    temperature       REAL NOT NULL,
    target_coverage   REAL NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('running','completed','failed')),
    final_status      TEXT,
    branch_coverage   REAL,
    mutation_score    REAL,
    attempts_json     TEXT,
    suspected_bugs    TEXT,
    created_at        TEXT NOT NULL,
    completed_at      TEXT
);

CREATE TABLE IF NOT EXISTS benchmark_entries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT REFERENCES runs(id),
    function      TEXT NOT NULL,
    mode          TEXT NOT NULL,
    branch_coverage REAL,
    mutation_score  REAL,
    caught_bug      INTEGER,        -- 1/0/NULL
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS testplans (
    id          TEXT PRIMARY KEY,
    spec_text   TEXT NOT NULL,
    model       TEXT NOT NULL,
    rows_json   TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS v_run_summary AS
SELECT
    id, function, mode, model, final_status,
    ROUND(branch_coverage * 100, 1) AS coverage_pct,
    ROUND(mutation_score * 100, 1)  AS mutation_pct,
    created_at
FROM runs;
"""


class Store:
    def __init__(self, db_path: str | Path):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(str(self._path))
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _init_db(self):
        with self._conn() as con:
            con.executescript(DDL)
            con.execute(
                "INSERT OR IGNORE INTO schema_meta VALUES (?,?)",
                ("version", "1"),
            )

    def save_run(self, report: RunReport) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._conn() as con:
            con.execute("""
                INSERT OR REPLACE INTO runs
                    (id, function, module_path, mode, model, prompt_version, temperature,
                     target_coverage, status, final_status, branch_coverage, mutation_score,
                     attempts_json, suspected_bugs, created_at, completed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                report.run_id, report.function, report.module_path,
                report.mode, report.model, report.prompt_version, report.temperature,
                report.target_coverage,
                "completed" if report.final_status != "error" else "failed",
                report.final_status,
                report.branch_coverage,
                report.mutation_score,
                json.dumps([a.model_dump() for a in report.attempts]),
                json.dumps(report.suspected_source_bugs),
                report.created_at,
                now,
            ))

    def save_benchmark_entry(self, run_id: str, function: str, mode: str,
                              branch_coverage: float, mutation_score: float | None,
                              caught_bug: bool | None) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._conn() as con:
            con.execute("""
                INSERT INTO benchmark_entries
                    (run_id, function, mode, branch_coverage, mutation_score, caught_bug, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (run_id, function, mode, branch_coverage, mutation_score,
                  (1 if caught_bug else 0) if caught_bug is not None else None, now))

    def list_runs(self, limit: int = 20) -> list[dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM v_run_summary ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_benchmark_summary(self) -> dict:
        with self._conn() as con:
            rows = con.execute("""
                SELECT mode,
                    AVG(branch_coverage) as mean_coverage,
                    AVG(mutation_score)  as mean_mutation,
                    SUM(caught_bug)      as bugs_caught,
                    COUNT(*)             as total
                FROM benchmark_entries
                GROUP BY mode
            """).fetchall()
        return {r["mode"]: dict(r) for r in rows}
