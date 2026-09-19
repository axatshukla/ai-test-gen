"""CI quality gate: exits 1 if benchmark metrics fall below thresholds."""
from __future__ import annotations
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def run_gate(db_path: str, min_mutation_score: float = 0.60, min_coverage: float = 0.75) -> int:
    """Return 0 (pass) or 1 (fail)."""
    from testgen.store import Store
    store = Store(db_path)
    summary = store.get_benchmark_summary()

    if not summary:
        console.print("[red]No benchmark data. Run testgen bench first.[/red]")
        return 1

    table = Table(title="Quality Gate Results", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Mode")
    table.add_column("Coverage", justify="right")
    table.add_column("Mutation", justify="right")
    table.add_column("Gate", justify="center")

    breaches = []
    for mode, data in summary.items():
        cov = data.get("mean_coverage") or 0.0
        mut = data.get("mean_mutation") or 0.0
        gate_ok = cov >= min_coverage and mut >= min_mutation_score
        status = "[green]PASS[/green]" if gate_ok else "[red]FAIL[/red]"
        table.add_row(mode, f"{cov:.0%}", f"{mut:.0%}", status)
        if not gate_ok:
            if cov < min_coverage:
                breaches.append(f"{mode} coverage {cov:.0%} < threshold {min_coverage:.0%}")
            if mut < min_mutation_score:
                breaches.append(f"{mode} mutation {mut:.0%} < threshold {min_mutation_score:.0%}")

    console.print(table)
    if breaches:
        console.print("\n[red bold]Gate FAILED:[/red bold]")
        for b in breaches:
            console.print(f"  {b}")
        return 1
    console.print("\n[green bold]Gate PASSED[/green bold]")
    return 0
