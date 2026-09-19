"""Benchmark runner: evaluates Code-Mode vs Spec-Mode across benchmark functions.
Empirically demonstrates the white-box contamination effect and planted bug catch rates.
"""
from __future__ import annotations
import json
import uuid
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich import box

from testgen.clients import get_client
from testgen.config import cfg
from testgen.extractor import extract_functions
from testgen.models import BenchmarkEntry, FunctionSpec
from testgen.mutator import score_mutation
from testgen.prompts import build_code_mode_prompt, build_spec_mode_prompt
from testgen.repair import generate_with_repair
from testgen.reporter import generate_benchmark_charts
from testgen.runner import run_tests

console = Console()
err = Console(stderr=True)


def catches_planted_bug(test_code: str, buggy_source: str) -> bool:
    """Return True if test_code fails against the buggy source code."""
    if not test_code.strip():
        return False
    result = run_tests(buggy_source, test_code, timeout=cfg.runner_timeout)
    return result.failed > 0 or result.errors > 0


def run_benchmark(
    functions_dir: Path,
    buggy_dir: Path,
    backend: str = "fake",
    model: str = "gpt-4o-mini",
    temperature: float = 0.2,
    target_coverage: float = 0.8,
    max_iters: int = 2,
    run_mutation: bool = True,
    out_dir: Optional[Path] = None,
    make_charts: bool = True,
    limit: Optional[int] = None,
) -> list[BenchmarkEntry]:
    """Run code-mode vs spec-mode benchmark across all functions in functions_dir."""
    out_dir = out_dir or Path(cfg.results_dir) / "benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)

    client = get_client(backend, model, cache_dir=cfg.cache_dir)
    py_files = sorted(functions_dir.glob("*.py"))
    # Skip __init__.py
    py_files = [f for f in py_files if f.name != "__init__.py"]

    entries: list[BenchmarkEntry] = []

    console.rule("[bold cyan]Running AI TestGen Benchmark (White-box vs Black-box)[/bold cyan]")
    console.print(f"Backend: [bold green]{backend}[/bold green] | Model: [bold green]{model}[/bold green]")
    console.print(f"Scanning: {functions_dir} | Buggy variants: {buggy_dir}")

    func_count = 0
    for py_file in py_files:
        clean_source = py_file.read_text(encoding="utf-8")
        buggy_path = buggy_dir / py_file.name
        buggy_source = buggy_path.read_text(encoding="utf-8") if buggy_path.exists() else None

        specs = extract_functions(str(py_file))
        for spec in specs:
            if limit and func_count >= limit:
                break
            func_count += 1

            console.print(f"--> Benchmarking [bold]{spec.name}[/bold] in {py_file.name}...")

            for mode in ("code", "spec"):
                run_id = f"bench_{uuid.uuid4().hex[:8]}"
                if mode == "code":
                    messages = build_code_mode_prompt(spec)
                else:
                    messages = build_spec_mode_prompt(spec)

                final_code, final_result, _ = generate_with_repair(
                    client=client,
                    initial_messages=messages,
                    module_source=clean_source,
                    function_name=spec.name,
                    mode=mode,
                    model=model,
                    temperature=temperature,
                    target_coverage=target_coverage,
                    max_iters=max_iters,
                )

                coverage = final_result.branch_coverage if final_result else 0.0
                mut_score = None
                if run_mutation and final_code and final_result:
                    mut_report = score_mutation(clean_source, final_code, max_mutants=cfg.max_mutants)
                    mut_score = mut_report.mutation_score

                caught = None
                if buggy_source and final_code:
                    caught = catches_planted_bug(final_code, buggy_source)

                entry = BenchmarkEntry(
                    function=spec.name,
                    mode=mode,
                    branch_coverage=coverage,
                    mutation_score=mut_score,
                    caught_bug=caught,
                    run_id=run_id,
                )
                entries.append(entry)
                try:
                    from testgen.store import Store
                    Store(cfg.db_path).save_benchmark_entry(
                        run_id=entry.run_id,
                        function=entry.function,
                        mode=entry.mode,
                        branch_coverage=entry.branch_coverage,
                        mutation_score=entry.mutation_score,
                        caught_bug=entry.caught_bug,
                    )
                except Exception as save_err:
                    pass

        if limit and func_count >= limit:
            break

    # Render results summary table
    table = Table(title="Benchmark Results: Code-Mode vs Spec-Mode", box=box.ROUNDED)
    table.add_column("Function", style="bold")
    table.add_column("Mode", justify="center")
    table.add_column("Coverage", justify="right")
    table.add_column("Mutation Score", justify="right")
    table.add_column("Planted Bug Caught?", justify="center")

    for e in entries:
        cov_str = f"{e.branch_coverage:.0%}"
        mut_str = f"{e.mutation_score:.0%}" if e.mutation_score is not None else "-"
        if e.caught_bug is True:
            bug_str = "[bold green]YES[/bold green]"
        elif e.caught_bug is False:
            bug_str = "[bold red]NO (missed)[/bold red]"
        else:
            bug_str = "[dim]N/A[/dim]"

        mode_color = "cyan" if e.mode == "code" else "yellow"
        table.add_row(e.function, f"[{mode_color}]{e.mode}[/{mode_color}]", cov_str, mut_str, bug_str)

    console.print(table)

    # Compute comparison metrics
    for m in ("code", "spec"):
        m_entries = [e for e in entries if e.mode == m]
        if m_entries:
            avg_cov = sum(e.branch_coverage for e in m_entries) / len(m_entries)
            valid_muts = [e.mutation_score for e in m_entries if e.mutation_score is not None]
            avg_mut = (sum(valid_muts) / len(valid_muts)) if valid_muts else 0.0
            bug_checks = [e for e in m_entries if e.caught_bug is not None]
            bug_rate = (sum(1 for e in bug_checks if e.caught_bug) / len(bug_checks)) if bug_checks else 0.0

            color = "cyan" if m == "code" else "yellow"
            console.print(
                f"[{color}]{m.upper()} MODE MEAN[/{color}]: "
                f"Coverage: [bold]{avg_cov:.1%}[/bold] | "
                f"Mutation Score: [bold]{avg_mut:.1%}[/bold] | "
                f"Planted Bug Catch Rate: [bold]{bug_rate:.1%}[/bold]"
            )

    # Save summary json
    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps([e.model_dump() for e in entries], indent=2), encoding="utf-8"
    )
    console.print(f"[green]Saved benchmark data to:[/green] {summary_path}")

    # Generate charts
    if make_charts and entries:
        try:
            generate_benchmark_charts(entries, out_dir)
        except Exception as ex:
            console.print(f"[yellow]Could not generate charts: {ex}[/yellow]")

    return entries