"""Central Pydantic data models. Defined first so every later module is guided by types."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, field_validator, Field
import time


class FunctionSpec(BaseModel):
    name: str
    qualname: str
    module_path: str
    signature: str
    params: list[tuple[str, str | None]]
    returns: str | None
    docstring: str | None
    source: str
    source_hash: str
    raises: list[str]
    decorators: list[str] = Field(default_factory=list)
    is_async: bool = False
    is_method: bool = False
    loc: int = 0
    complexity: int = 1


class SanitizeResult(BaseModel):
    ok: bool
    code: str = ""
    error: str = ""


class FailureDetail(BaseModel):
    test_name: str
    traceback: str


class RunResult(BaseModel):
    passed: int
    failed: int
    errors: int
    xfailed: int
    branch_coverage: float
    uncovered_lines: list[tuple[int, str]] = Field(default_factory=list)
    failure_details: list[FailureDetail] = Field(default_factory=list)
    raw_ok: bool = True
    error_message: str = ""


class LLMResponse(BaseModel):
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


class GenerationAttempt(BaseModel):
    attempt_number: int
    raw_response: str = ""
    sanitize_ok: bool = False
    sanitize_error: str = ""
    run_result: RunResult | None = None
    llm_error: str = ""
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


class RunReport(BaseModel):
    run_id: str
    function: str
    module_path: str
    mode: Literal["code", "spec"]
    model: str
    prompt_version: str
    temperature: float
    target_coverage: float
    attempts: list[GenerationAttempt] = Field(default_factory=list)
    final_code: str = ""
    final_status: Literal["passed", "coverage_not_met", "failed", "error"] = "error"
    branch_coverage: float = 0.0
    mutation_score: float | None = None
    suspected_source_bugs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    completed_at: str = ""


class MutantResult(BaseModel):
    mutant_source: str
    killed: bool
    killing_test: str = ""
    outcome: Literal["killed", "survived", "timeout", "error"] = "survived"


class MutationReport(BaseModel):
    mutants_total: int
    mutants_killed: int
    mutation_score: float | None
    results: list[MutantResult] = Field(default_factory=list)


class TestPlanRow(BaseModel):
    id: str
    category: Literal["functional", "boundary", "negative", "security", "performance", "concurrency"]
    precondition: str
    steps: str
    expected_result: str
    priority: Literal["P0", "P1", "P2"]

    @field_validator("steps", mode="before")
    @classmethod
    def normalize_steps(cls, v):
        if isinstance(v, list):
            return " -> ".join(str(s) for s in v)
        return str(v)

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v):
        s = str(v).strip().upper()
        return s if s in ("P0", "P1", "P2") else "P1"

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        s = str(v).strip().lower()
        valid = {"functional", "boundary", "negative", "security", "performance", "concurrency"}
        return s if s in valid else "functional"


class TestPlan(BaseModel):
    testplan_id: str
    spec_text: str
    model: str
    rows: list[TestPlanRow] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


class BenchmarkEntry(BaseModel):
    function: str
    mode: Literal["code", "spec"]
    branch_coverage: float
    mutation_score: float | None
    caught_bug: bool | None
    run_id: str = ""