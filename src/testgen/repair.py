"""Bounded repair loop: generate -> sanitize -> run -> repair (max N iterations)."""
from __future__ import annotations
from pathlib import Path
import json
import time

from testgen.clients.base import LLMClient, LLMError
from testgen.config import cfg
from testgen.models import GenerationAttempt, RunResult
from testgen.prompts import build_repair_prompt
from testgen.sanitizer import sanitize
from testgen.runner import run_tests


def generate_with_repair(
    client: LLMClient,
    initial_messages: list[dict],
    module_source: str,
    function_name: str = "unknown",
    mode: str = "code",
    model: str = "unknown",
    prompt_version: str = "v3",
    temperature: float | None = None,
    target_coverage: float | None = None,
    max_iters: int | None = None,
    log_path: Path | None = None,
) -> tuple[str, RunResult | None, list[GenerationAttempt]]:
    """
    Run the bounded repair loop.

    Returns:
        (final_code, final_run_result, list_of_attempts)
    final_run_result is None if every attempt failed at LLM or sanitization.
    """
    _temperature      = temperature      if temperature      is not None else cfg.temperature
    _target_coverage  = target_coverage  if target_coverage  is not None else cfg.target_coverage
    _max_iters        = max_iters        if max_iters        is not None else cfg.max_iterations

    messages = initial_messages
    final_code = ""
    final_result: RunResult | None = None
    attempts: list[GenerationAttempt] = []

    for attempt_num in range(1, _max_iters + 1):
        attempt = GenerationAttempt(attempt_number=attempt_num)

        # Step 1: call LLM
        try:
            resp = client.generate(messages, temperature=_temperature)
            attempt.raw_response = resp.text
        except LLMError as e:
            attempt.llm_error = str(e)
            attempts.append(attempt)
            continue

        # Step 2: sanitize
        san = sanitize(resp.text)
        if not san.ok:
            attempt.sanitize_ok = False
            attempt.sanitize_error = san.error
            attempts.append(attempt)
            # Feed back sanitization failure
            messages = initial_messages + [
                {"role": "assistant", "content": resp.text},
                {"role": "user",      "content":
                    f"Your output failed a static safety check: {san.error}. "
                    f"Fix this and regenerate following all rules."},
            ]
            continue

        attempt.sanitize_ok = True
        final_code = san.code

        # Step 3: run tests
        result = run_tests(module_source, san.code, timeout=cfg.runner_timeout)
        attempt.run_result = result
        attempts.append(attempt)
        final_result = result

        # Step 4: check stop condition
        if result.failed == 0 and result.errors == 0 and result.branch_coverage >= _target_coverage:
            break

        if attempt_num < _max_iters:
            # Build repair context
            failure_summary = "\n".join(
                f"- {f.test_name}:\n  {f.traceback[:400]}"
                for f in result.failure_details
            ) or "(no failing tests -- branch coverage target not met)"
            messages = build_repair_prompt(san.code, failure_summary, result.uncovered_lines)

    # Persist attempt log
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_data = [a.model_dump() for a in attempts]
        log_path.write_text(json.dumps(log_data, indent=2), encoding="utf-8")

    return final_code, final_result, attempts
