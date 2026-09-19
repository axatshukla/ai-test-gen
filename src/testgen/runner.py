"""Sandboxed pytest runner using subprocess with coverage.py in branch mode."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from testgen.models import FailureDetail, RunResult


def run_tests(
    module_source: str,
    test_code: str,
    timeout: int = 30,
) -> RunResult:
    """
    Write module + test into an isolated temp directory, run pytest with branch
    coverage, parse both JSON reports, and return a RunResult.

    The temp directory is always cleaned up, even on timeout.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="testgen_"))
    try:
        (tmpdir / "module_under_test.py").write_text(module_source, encoding="utf-8")
        (tmpdir / "test_generated.py").write_text(test_code, encoding="utf-8")
        cov_json_name = "cov.json"
        report_json_name = "report.json"

        cmd = [
            sys.executable, "-m", "pytest",
            "test_generated.py",
            "--cov=module_under_test",
            "--cov-branch",
            f"--cov-report=json:{cov_json_name}",
            "--json-report",
            f"--json-report-file={report_json_name}",
            "-q", "--tb=short",
        ]

        # Strip API keys and sensitive env vars from subprocess environment
        safe_env = {k: v for k, v in os.environ.items()
                    if not any(sensitive in k.upper()
                               for sensitive in ("KEY", "SECRET", "TOKEN", "PASSWORD"))}

        try:
            subprocess.run(
                cmd, cwd=tmpdir,
                timeout=timeout,
                capture_output=True,
                text=True,
                env=safe_env,
            )
        except subprocess.TimeoutExpired:
            return RunResult(
                passed=0, failed=0, errors=0, xfailed=0,
                branch_coverage=0.0, raw_ok=False,
                error_message="execution_timeout",
            )

        report_json = tmpdir / report_json_name
        if not report_json.exists():
            return RunResult(
                passed=0, failed=0, errors=0, xfailed=0,
                branch_coverage=0.0, raw_ok=False,
                error_message="pytest_did_not_produce_report",
            )

        # Parse pytest JSON report
        report = json.loads(report_json.read_text(encoding="utf-8"))
        summary = report.get("summary", {})
        failure_details: list[FailureDetail] = []
        for test in report.get("tests", []):
            if test.get("outcome") == "failed":
                longrepr = str(test.get("call", {}).get("longrepr", ""))[:2000]
                failure_details.append(FailureDetail(
                    test_name=test.get("nodeid", "?"),
                    traceback=longrepr,
                ))

        # Parse coverage JSON report
        branch_coverage = 0.0
        uncovered_lines: list[tuple[int, str]] = []
        cov_json = tmpdir / cov_json_name
        if cov_json.exists():
            cov = json.loads(cov_json.read_text(encoding="utf-8"))
            mod = cov.get("files", {}).get("module_under_test.py", {})
            branch_coverage = mod.get("summary", {}).get("percent_covered", 0.0) / 100.0
            src_lines = module_source.splitlines()
            for ln in mod.get("missing_lines", []):
                if 1 <= ln <= len(src_lines):
                    uncovered_lines.append((ln, src_lines[ln - 1].strip()))

        return RunResult(
            passed=summary.get("passed", 0),
            failed=summary.get("failed", 0),
            errors=summary.get("error", 0),
            xfailed=summary.get("xfailed", 0),
            branch_coverage=branch_coverage,
            uncovered_lines=uncovered_lines,
            failure_details=failure_details,
            raw_ok=True,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
