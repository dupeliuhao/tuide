"""Search helpers for files and text within the workspace."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class SearchService:
    """Linux-first filesystem search helpers.

    Prefers ``fd`` (file search) and ``rg`` (text search) when they are on
    PATH; falls back to pure-Python iteration when they are not.
    """

    TEXT_EXTENSIONS = {
        ".py",
        ".scala",
        ".sc",
        ".sbt",
        ".sql",
        ".hql",
        ".md",
        ".txt",
        ".sh",
        ".bash",
        ".zsh",
        ".toml",
        ".json",
        ".yaml",
        ".yml",
        ".csv",
        ".tsv",
    }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def find_files(self, roots: list[Path], query: str, limit: int = 200) -> list[Path]:
        """Return matching files across workspace roots."""
        if shutil.which("fd"):
            return self._find_files_fd(roots, query, limit)
        return self._find_files_python(roots, query, limit)

    def search_workspace_text(self, roots: list[Path], query: str, limit: int = 500) -> list[str]:
        """Search text across workspace roots and return formatted matches."""
        if not query.strip():
            return []
        if shutil.which("rg"):
            return self._search_rg(roots, query, limit)
        return self._search_python(roots, query, limit)

    # ------------------------------------------------------------------ #
    # fd backend
    # ------------------------------------------------------------------ #

    def _find_files_fd(self, roots: list[Path], query: str, limit: int) -> list[Path]:
        valid_roots = [str(r) for r in roots if r.exists()]
        if not valid_roots:
            return []
        args = ["fd", "--type", "f", "--max-results", str(limit)]
        if query.strip():
            args.append(query.strip())
        args.extend(valid_roots)
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=15)
            if result.returncode not in (0, 1):
                return self._find_files_python(roots, query, limit)
            paths = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
            return paths[:limit]
        except (subprocess.TimeoutExpired, OSError):
            return self._find_files_python(roots, query, limit)

    # ------------------------------------------------------------------ #
    # ripgrep backend
    # ------------------------------------------------------------------ #

    def _search_rg(self, roots: list[Path], query: str, limit: int) -> list[str]:
        valid_roots = [str(r) for r in roots if r.exists()]
        if not valid_roots:
            return []
        args = [
            "rg",
            "--line-number",
            "--with-filename",
            "--no-heading",
            "--max-count", "1",  # at most 1 match per file keeps output manageable
            query,
        ] + valid_roots
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            if result.returncode not in (0, 1):  # 1 = no matches
                return self._search_python(roots, query, limit)
            lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            return lines[:limit]
        except (subprocess.TimeoutExpired, OSError):
            return self._search_python(roots, query, limit)

    # ------------------------------------------------------------------ #
    # Pure-Python fallbacks
    # ------------------------------------------------------------------ #

    def _find_files_python(self, roots: list[Path], query: str, limit: int) -> list[Path]:
        normalized = query.lower().strip()
        matches: list[Path] = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if normalized and normalized not in path.name.lower():
                    continue
                matches.append(path)
                if len(matches) >= limit:
                    return matches
        return matches

    def _search_python(self, roots: list[Path], query: str, limit: int) -> list[str]:
        normalized = query.strip()
        matches: list[str] = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in self.TEXT_EXTENSIONS:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if normalized not in line:
                        continue
                    matches.append(f"{path}:{line_number}: {line.strip()}")
                    if len(matches) >= limit:
                        return matches
        return matches
