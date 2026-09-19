"""AST-based mutation testing engine.
Generates one mutant per AST node site (standard mutation testing practice).
Capped at max_mutants per function to keep benchmark runs tractable.
"""
from __future__ import annotations
import ast
import copy

from testgen.models import MutantResult, MutationReport
from testgen.runner import run_tests

# Operator flip tables
_COMPARISON_FLIPS = {
    ast.Lt: ast.LtE, ast.LtE: ast.Lt,
    ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
}
_ARITHMETIC_FLIPS = {
    ast.Add: ast.Sub, ast.Sub: ast.Add,
    ast.Mult: ast.Div, ast.Div: ast.Mult,
}
_BOOL_FLIPS = {
    ast.And: ast.Or, ast.Or: ast.And,
}


def _find_mutable_sites(tree: ast.AST) -> list[tuple]:
    """Walk the tree and collect all mutable (node, index, kind) triples."""
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in _COMPARISON_FLIPS:
                    sites.append((node, i, "cmp"))
        elif isinstance(node, ast.BinOp) and type(node.op) in _ARITHMETIC_FLIPS:
            sites.append((node, None, "arith"))
        elif isinstance(node, ast.BoolOp) and type(node.op) in _BOOL_FLIPS:
            sites.append((node, None, "bool"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            sites.append((node, None, "const_bool"))
        elif isinstance(node, ast.Return) and node.value is not None:
            sites.append((node, None, "return_none"))
    return sites


def generate_mutants(source: str, max_mutants: int = 30) -> list[str]:
    """Generate up to max_mutants single-mutation variants of source."""
    try:
        base_tree = ast.parse(source)
    except SyntaxError:
        return []

    all_nodes = list(ast.walk(base_tree))
    sites = _find_mutable_sites(base_tree)
    mutants = []

    for node, idx, kind in sites[:max_mutants]:
        try:
            node_pos = all_nodes.index(node)
        except ValueError:
            continue

        tree_copy = copy.deepcopy(base_tree)
        copy_nodes = list(ast.walk(tree_copy))
        if node_pos >= len(copy_nodes):
            continue
        target = copy_nodes[node_pos]

        try:
            if kind == "cmp":
                target.ops[idx] = _COMPARISON_FLIPS[type(target.ops[idx])]()
            elif kind == "arith":
                target.op = _ARITHMETIC_FLIPS[type(target.op)]()
            elif kind == "bool":
                target.op = _BOOL_FLIPS[type(target.op)]()
            elif kind == "const_bool":
                target.value = not target.value
            elif kind == "return_none":
                target.value = ast.Constant(value=None)

            ast.fix_missing_locations(tree_copy)
            mutants.append(ast.unparse(tree_copy))
        except Exception:
            continue

    return mutants


def score_mutation(
    module_source: str,
    test_code: str,
    max_mutants: int = 30,
    timeout: int = 20,
) -> MutationReport:
    """
    Generate mutants from module_source, run test_code against each,
    and return a MutationReport.
    """
    mutants = generate_mutants(module_source, max_mutants=max_mutants)
    results: list[MutantResult] = []
    killed = 0

    for mutant_src in mutants:
        result = run_tests(mutant_src, test_code, timeout=timeout)
        is_killed = result.failed > 0 or result.errors > 0
        if is_killed:
            killed += 1
            killing_test = result.failure_details[0].test_name if result.failure_details else ""
            outcome = "killed"
        elif result.error_message == "execution_timeout":
            outcome = "timeout"
        elif not result.raw_ok:
            outcome = "error"
        else:
            outcome = "survived"

        results.append(MutantResult(
            mutant_source=mutant_src,
            killed=is_killed,
            killing_test=killing_test if is_killed else "",
            outcome=outcome,
        ))

    total = len(mutants)
    score = (killed / total) if total > 0 else None

    return MutationReport(
        mutants_total=total,
        mutants_killed=killed,
        mutation_score=score,
        results=results,
    )
