"""Project-aware Python navigation powered by Jedi."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import jedi
import jedi.settings


@dataclass(frozen=True, slots=True)
class PythonNavigationTarget:
    """A resolved navigation target."""

    path: Path
    line: int
    column: int
    name: str
    kind: str
    preview: str


class PythonNavigationService:
    """Resolve Python definitions and references across a workspace."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or Path("/tmp/tuide-jedi-cache")

    def available_for(self, path: Path | None) -> bool:
        """Return whether Python navigation should run for the path."""
        return path is not None and path.suffix.lower() == ".py"

    def goto_definition(
        self,
        path: Path,
        text: str,
        line: int,
        column: int,
        workspace_roots: list[Path],
    ) -> list[PythonNavigationTarget]:
        """Resolve definitions for the symbol at the given location."""
        script = self._build_script(path, text, workspace_roots)
        names = script.goto(
            line,
            max(column - 1, 0),
            follow_imports=True,
            follow_builtin_imports=False,
        )
        return self._normalize_results(names, workspace_roots, current_path=path, current_text=text)

    def find_references(
        self,
        path: Path,
        text: str,
        line: int,
        column: int,
        workspace_roots: list[Path],
    ) -> list[PythonNavigationTarget]:
        """Resolve references for the symbol at the given location."""
        script = self._build_script(path, text, workspace_roots)
        names = script.get_references(
            line,
            max(column - 1, 0),
            include_builtins=False,
        )
        return self._normalize_results(names, workspace_roots, current_path=path, current_text=text)

    def _build_script(self, path: Path, text: str, workspace_roots: list[Path]) -> jedi.Script:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        jedi.settings.cache_directory = str(self.cache_dir)
        project_root = self._project_root_for(path, workspace_roots)
        project = jedi.Project(
            path=str(project_root),
            environment_path=sys.prefix,
        )
        return jedi.Script(code=text, path=str(path), project=project)

    def _normalize_results(
        self,
        names: list,
        workspace_roots: list[Path],
        *,
        current_path: Path,
        current_text: str,
    ) -> list[PythonNavigationTarget]:
        results: list[PythonNavigationTarget] = []
        seen: set[tuple[Path, int, int]] = set()
        resolved_roots = [root.resolve() for root in workspace_roots if root.exists()]

        for name in names:
            module_path = getattr(name, "module_path", None)
            line = getattr(name, "line", None)
            column = getattr(name, "column", None)
            if module_path is None or line is None or column is None:
                continue

            target_path = Path(module_path)
            try:
                resolved_path = target_path.resolve()
            except OSError:
                continue
            if resolved_roots and not any(
                resolved_path == root or root in resolved_path.parents for root in resolved_roots
            ):
                continue

            key = (resolved_path, int(line), int(column) + 1)
            if key in seen:
                continue
            seen.add(key)

            results.append(
                PythonNavigationTarget(
                    path=resolved_path,
                    line=int(line),
                    column=int(column) + 1,
                    name=getattr(name, "name", resolved_path.stem),
                    kind=getattr(name, "type", "symbol"),
                    preview=self._line_preview(
                        resolved_path,
                        int(line),
                        current_path=current_path,
                        current_text=current_text,
                    ),
                )
            )

        results.sort(key=lambda item: (str(item.path), item.line, item.column))
        return results

    @staticmethod
    def _project_root_for(path: Path, workspace_roots: list[Path]) -> Path:
        resolved_path = path.resolve()
        for root in workspace_roots:
            try:
                resolved_root = root.resolve()
            except OSError:
                continue
            if resolved_path == resolved_root or resolved_root in resolved_path.parents:
                return resolved_root
        return resolved_path.parent

    @staticmethod
    def _line_preview(path: Path, line_number: int, *, current_path: Path, current_text: str) -> str:
        if path == current_path:
            lines = current_text.splitlines()
        else:
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                return ""

        if 1 <= line_number <= len(lines):
            return lines[line_number - 1].strip()
        return ""
