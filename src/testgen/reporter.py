"""Rich terminal output and Matplotlib chart generation."""
from __future__ import annotations
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import box
from testgen.models import RunReport, BenchmarkEntry

console = Console()


def print_run_summary(report: RunReport) -> None:
    table = Table(title=f"testgen -- {report.function} ({report.mode} mode)",
                  box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim", width=22)
    table.add_column("Value", justify="right")
    final = report.attempts[-1].run_result if report.attempts else None
    passed  = final.passed  if final else "?"
    failed  = final.failed  if final else "?"
    xfailed = final.xfailed if final else "?"
    coverage = f"{final.branch_coverage:.0%}" if final else "?"
    mutation = f"{report.mutation_score:.0%}" if report.mutation_score is not None else "?"
    color = {"passed":"green","coverage_not_met":"yellow","failed":"red","error":"red"}.get(report.final_status,"white")
    table.add_row("Status", f"[{color}]{report.final_status}[/{color}]")
    table.add_row("Tests passed",    str(passed))
    table.add_row("Tests failed",    str(failed))
    table.add_row("XFailed",         str(xfailed))
    table.add_row("Branch coverage", coverage)
    table.add_row("Mutation score",  mutation)
    table.add_row("Iterations used", str(len(report.attempts)))
    table.add_row("Model",           report.model)
    console.print(table)
    if report.suspected_source_bugs:
        console.print("\n[yellow]Suspected source bugs:[/yellow]")
        for b in report.suspected_source_bugs:
            console.print(f"  {b}")


def write_json_report(report: RunReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "report.json"
    p.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return p


def write_markdown_report(report: RunReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    final = report.attempts[-1].run_result if report.attempts else None
    cov = f"{final.branch_coverage:.0%}" if final else "?"
    mut = f"{report.mutation_score:.0%}" if report.mutation_score is not None else "?"
    lines = [
        f"# testgen report -- {report.function}", "",
        "| Field | Value |", "|---|---|",
        f"| Function | `{report.function}` |",
        f"| Mode | {report.mode} |",
        f"| Model | {report.model} |",
        f"| Final status | **{report.final_status}** |",
        f"| Branch coverage | {cov} |",
        f"| Mutation score | {mut} |",
        f"| Iterations | {len(report.attempts)} |", "",
    ]
    p = out_dir / "report.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def generate_benchmark_charts(entries: list[BenchmarkEntry], out_dir: Path) -> None:
    import matplotlib.pyplot as plt
    out_dir.mkdir(parents=True, exist_ok=True)
    modes = ["code", "spec"]
    colors = ["#4A90D9", "#E87040"]

    covs = []
    for m in modes:
        vals = [e.branch_coverage for e in entries if e.mode == m]
        covs.append(sum(vals) / len(vals) if vals else 0.0)
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(modes, [c * 100 for c in covs], color=colors, edgecolor="white")
    ax.bar_label(bars, fmt="%.1f%%", padding=4)
    ax.set_title("Mean Branch Coverage by Mode", fontsize=14, fontweight="bold")
    ax.set_ylabel("Branch Coverage (%)")
    ax.set_ylim(0, 110)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_dir / "coverage_by_mode.png", dpi=150)
    plt.close(fig)

    bug_rates = []
    for m in modes:
        bug_entries = [e for e in entries if e.mode == m and e.caught_bug is not None]
        rate = sum(1 for e in bug_entries if e.caught_bug) / len(bug_entries) if bug_entries else 0.0
        bug_rates.append(rate)
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(modes, [r * 100 for r in bug_rates], color=colors, edgecolor="white")
    ax.bar_label(bars, fmt="%.1f%%", padding=4)
    ax.set_title("Planted Bug Detection Rate by Mode", fontsize=14, fontweight="bold")
    ax.set_ylabel("Detection Rate (%)")
    ax.set_ylim(0, 110)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_dir / "bugs_caught_by_mode.png", dpi=150)
    plt.close(fig)
    console.print(f"[green]Charts saved to {out_dir}/[/green]")
