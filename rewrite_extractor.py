import pathlib
enc = "utf-8"

files = {
    "src/testgen/extractor.py": r"""
from __future__ import annotations
import ast
import hashlib
from testgen.models import FunctionSpec


def _extract_raises(node: ast.AST) -> list[str]:
    raised = []
    for n in ast.walk(node):
        if isinstance(n, ast.Raise) and n.exc is not None:
            target = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
            try:
                raised.append(ast.unparse(target))
            except Exception:
                pass
    seen, out = set(), []
    for r in raised:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _render_signature(node) -> str:
    args = []
    for a in node.args.args:
        if a.arg == "self":
            continue
        ann = f": {ast.unparse(a.annotation)}" if a.annotation else ""
        args.append(f"{a.arg}{ann}")
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    joined = ", ".join(args)
    return f"{node.name}({joined}){ret}"


def _params(node) -> list[tuple[str, str | None]]:
    result = []
    for a in node.args.args:
        if a.arg == "self":
            continue
        ann = ast.unparse(a.annotation) if a.annotation else None
        result.append((a.arg, ann))
    return result


def _cyclomatic_complexity(node: ast.AST) -> int:
    branch_types = (ast.If, ast.For, ast.While, ast.ExceptHandler,
                    ast.With, ast.Assert, ast.comprehension)
    return 1 + sum(1 for n in ast.walk(node) if isinstance(n, branch_types))


def extract_functions(path: str, function_name: str | None = None) -> list[FunctionSpec]:
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src, filename=path)
    specs: list[FunctionSpec] = []

    class _Visitor(ast.NodeVisitor):
        def __init__(self):
            self._class: str | None = None

        def visit_ClassDef(self, node: ast.ClassDef):
            prev, self._class = self._class, node.name
            self.generic_visit(node)
            self._class = prev

        def _handle_func(self, node):
            if node.name.startswith("_") and function_name is None:
                return
            qualname = f"{self._class}.{node.name}" if self._class else node.name
            source = ast.unparse(node)
            specs.append(FunctionSpec(
                name=node.name,
                qualname=qualname,
                module_path=path,
                signature=_render_signature(node),
                params=_params(node),
                returns=ast.unparse(node.returns) if node.returns else None,
                docstring=ast.get_docstring(node),
                source=source,
                source_hash=hashlib.sha256(source.encode()).hexdigest(),
                raises=_extract_raises(node),
                decorators=[ast.unparse(d) for d in node.decorator_list],
                is_async=isinstance(node, ast.AsyncFunctionDef),
                is_method=self._class is not None,
                loc=(node.end_lineno or node.lineno) - node.lineno + 1,
                complexity=_cyclomatic_complexity(node),
            ))

        def visit_FunctionDef(self, node):
            self._handle_func(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node):
            self._handle_func(node)
            self.generic_visit(node)

    _Visitor().visit(tree)
    if function_name:
        specs = [s for s in specs if function_name in (s.name, s.qualname)]
    return specs
""",
}

for path, content in files.items():
    p = pathlib.Path(path)
    p.write_text(content.lstrip(), encoding=enc)
    print(f"Written: {path} ({len(p.read_bytes())} bytes)")
