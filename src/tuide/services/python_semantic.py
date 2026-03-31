"""Lightweight Python semantic analysis for definitions and usages."""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SymbolOccurrence:
    """A single symbol occurrence."""

    name: str
    kind: str
    line: int
    column: int


class _SemanticVisitor(ast.NodeVisitor):
    """Collect function, class, and symbol usage data."""

    def __init__(self) -> None:
        self.definitions: list[SymbolOccurrence] = []
        self.usages: dict[str, list[SymbolOccurrence]] = defaultdict(list)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_function(node, "function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_function(node, "async function")
        self.generic_visit(node)

    def _record_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
        self.definitions.append(SymbolOccurrence(node.name, kind, node.lineno, node.col_offset + 1))
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            self.usages[arg.arg].append(
                SymbolOccurrence(arg.arg, "parameter", arg.lineno, arg.col_offset + 1)
            )
        if node.args.vararg is not None:
            arg = node.args.vararg
            self.usages[arg.arg].append(
                SymbolOccurrence(arg.arg, "parameter", arg.lineno, arg.col_offset + 1)
            )
        if node.args.kwarg is not None:
            arg = node.args.kwarg
            self.usages[arg.arg].append(
                SymbolOccurrence(arg.arg, "parameter", arg.lineno, arg.col_offset + 1)
            )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.definitions.append(SymbolOccurrence(node.name, "class", node.lineno, node.col_offset + 1))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        callee = self._call_name(node.func)
        if callee is not None:
            self.usages[callee].append(SymbolOccurrence(callee, "call", node.lineno, node.col_offset + 1))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        kind = "read" if isinstance(node.ctx, ast.Load) else "write"
        self.usages[node.id].append(SymbolOccurrence(node.id, kind, node.lineno, node.col_offset + 1))
        self.generic_visit(node)

    @staticmethod
    def _call_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None


class PythonSemanticService:
    """Provide a lightweight semantic summary for Python files."""

    def available_for(self, path: Path | None) -> bool:
        """Return whether semantic analysis should run for the path."""
        return path is not None and path.suffix.lower() == ".py"

    def build_outline(self, path: Path, text: str) -> str:
        """Build a semantic outline for a Python file."""
        tree = self._parse(text)
        if tree is None:
            return f"Semantic outline unavailable for {path.name}.\n\nThe file currently contains syntax errors."

        visitor = _SemanticVisitor()
        visitor.visit(tree)

        lines = [f"Python semantic outline for {path}", ""]
        lines.append("Definitions")
        if visitor.definitions:
            for item in sorted(visitor.definitions, key=lambda occurrence: (occurrence.line, occurrence.column)):
                lines.append(f"  {item.kind:<14} {item.name}  (line {item.line})")
        else:
            lines.append("  No function or class definitions found.")

        lines.append("")
        lines.append("Usage summary")
        interesting_names = {
            item.name for item in visitor.definitions if item.kind in {"function", "async function", "class"}
        }
        if interesting_names:
            for name in sorted(interesting_names):
                occurrences = visitor.usages.get(name, [])
                rendered = ", ".join(f"{entry.kind}@{entry.line}" for entry in occurrences[:10]) or "no references found"
                lines.append(f"  {name}: {rendered}")
        else:
            lines.append("  No symbol usage summary available.")
        return "\n".join(lines)

    def symbol_report(self, path: Path, text: str, line: int, column: int) -> str:
        """Return a focused report for the symbol near the cursor."""
        symbol = self.symbol_at_position(text, line, column)
        if symbol is None:
            return (
                f"Python semantic details for {path}\n\n"
                "No symbol was found at the current cursor location."
            )

        tree = self._parse(text)
        if tree is None:
            return (
                f"Python semantic details for {path}\n\n"
                f"Current symbol: {symbol}\n"
                "Semantic analysis is unavailable until the file parses."
            )

        visitor = _SemanticVisitor()
        visitor.visit(tree)
        definitions = [item for item in visitor.definitions if item.name == symbol]
        usages = visitor.usages.get(symbol, [])

        lines = [f"Python semantic details for {path}", "", f"Symbol: {symbol}", ""]
        lines.append("Definitions")
        if definitions:
            for item in definitions:
                lines.append(f"  {item.kind} at line {item.line}, column {item.column}")
        else:
            lines.append("  No definition found in the current file.")

        lines.append("")
        lines.append("Usages")
        if usages:
            for item in usages[:40]:
                lines.append(f"  {item.kind} at line {item.line}, column {item.column}")
        else:
            lines.append("  No usages found in the current file.")
        return "\n".join(lines)

    def symbol_at_position(self, text: str, line: int, column: int) -> str | None:
        """Return the identifier at a 1-based cursor location."""
        lines = text.splitlines()
        if line <= 0 or line > len(lines):
            return None
        row = lines[line - 1]
        if not row:
            return None

        index = min(max(column - 1, 0), len(row) - 1)
        if not (row[index].isalnum() or row[index] == "_"):
            if index > 0 and (row[index - 1].isalnum() or row[index - 1] == "_"):
                index -= 1
            else:
                return None

        start = index
        end = index + 1
        while start > 0 and (row[start - 1].isalnum() or row[start - 1] == "_"):
            start -= 1
        while end < len(row) and (row[end].isalnum() or row[end] == "_"):
            end += 1
        return row[start:end]

    @staticmethod
    def _parse(text: str) -> ast.AST | None:
        try:
            return ast.parse(text)
        except SyntaxError:
            return None
