"""Search helpers for files and text within the workspace."""

from __future__ import annotations

import re
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

    def search_workspace_text_locations(
        self,
        roots: list[Path],
        query: str,
        limit: int = 200,
    ) -> list[tuple[str, int, int, str]]:
        """Search text across workspace roots and return openable locations."""
        if not query.strip():
            return []
        if shutil.which("rg"):
            return self._search_rg_locations(roots, query, limit)
        return self._search_python_locations(roots, query, limit)

    def search_workspace_names(
        self,
        roots: list[Path],
        query: str,
        limit: int = 200,
    ) -> list[tuple[str, int, int, str]]:
        """Search file names plus lightweight Python class/function names."""
        normalized = query.strip()
        if not normalized:
            return []

        results: list[tuple[str, int, int, str]] = []
        seen: set[tuple[str, int, int, str]] = set()

        file_limit = max(1, limit // 2)
        for path in self.find_files(roots, normalized, limit=file_limit):
            if path.suffix.lower() == ".pyc" or "__pycache__" in path.parts:
                continue
            resolved = path.resolve()
            item = (str(resolved), 1, 1, f"[file] {resolved.name} — {resolved.parent}")
            if item in seen:
                continue
            seen.add(item)
            results.append(item)
            if len(results) >= limit:
                return results

        remaining = max(0, limit - len(results))
        if remaining == 0:
            return results

        if shutil.which("rg"):
            symbol_results = self._search_python_defs_rg(roots, normalized, remaining)
        else:
            symbol_results = self._search_python_defs_python(roots, normalized, remaining)

        for item in symbol_results:
            if item in seen:
                continue
            seen.add(item)
            results.append(item)
            if len(results) >= limit:
                break
        return results

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
            "--fixed-strings",
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

    def _search_rg_locations(
        self,
        roots: list[Path],
        query: str,
        limit: int,
    ) -> list[tuple[str, int, int, str]]:
        valid_roots = [str(r) for r in roots if r.exists()]
        if not valid_roots:
            return []
        args = [
            "rg",
            "--line-number",
            "--column",
            "--with-filename",
            "--no-heading",
            "--fixed-strings",
            "--smart-case",
            query,
        ] + valid_roots
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            if result.returncode not in (0, 1):
                return self._search_python_locations(roots, query, limit)
            matches: list[tuple[str, int, int, str]] = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    path_part, line_part, column_part, snippet = line.split(":", 3)
                    matches.append((path_part, int(line_part), int(column_part), snippet.strip()))
                except (ValueError, IndexError):
                    continue
                if len(matches) >= limit:
                    break
            return matches
        except (subprocess.TimeoutExpired, OSError):
            return self._search_python_locations(roots, query, limit)

    def _search_python_defs_rg(
        self,
        roots: list[Path],
        query: str,
        limit: int,
    ) -> list[tuple[str, int, int, str]]:
        valid_roots = [str(r) for r in roots if r.exists()]
        if not valid_roots:
            return []
        pattern = r"^\s*(?:class|(?:async\s+)?def)\s+[A-Za-z_][A-Za-z0-9_]*"
        args = [
            "rg",
            "--line-number",
            "--column",
            "--with-filename",
            "--no-heading",
            "--smart-case",
            "--glob",
            "*.py",
            pattern,
        ] + valid_roots
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            if result.returncode not in (0, 1):
                return self._search_python_defs_python(roots, query, limit)
            matches: list[tuple[str, int, int, str]] = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    path_part, line_part, column_part, snippet = line.split(":", 3)
                    rendered = snippet.strip()
                    name_match = re.search(r"(?:class|(?:async\s+)?def)\s+([A-Za-z_][A-Za-z0-9_]*)", rendered)
                    if name_match is None or query.lower() not in name_match.group(1).lower():
                        continue
                    if rendered.startswith("class "):
                        rendered = f"[class] {rendered}"
                    else:
                        rendered = f"[symbol] {rendered}"
                    matches.append((path_part, int(line_part), int(column_part), rendered))
                except (ValueError, IndexError):
                    continue
                if len(matches) >= limit:
                    break
            return matches
        except (subprocess.TimeoutExpired, OSError):
            return self._search_python_defs_python(roots, query, limit)

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

    def _search_python_locations(
        self,
        roots: list[Path],
        query: str,
        limit: int,
    ) -> list[tuple[str, int, int, str]]:
        normalized = query.strip()
        matches: list[tuple[str, int, int, str]] = []
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
                    column = line.find(normalized)
                    if column < 0:
                        continue
                    matches.append((str(path), line_number, column + 1, line.strip()))
                    if len(matches) >= limit:
                        return matches
        return matches

    def _search_python_defs_python(
        self,
        roots: list[Path],
        query: str,
        limit: int,
    ) -> list[tuple[str, int, int, str]]:
        pattern = re.compile(r"^\s*(class|(?:async\s+)?def)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
        matches: list[tuple[str, int, int, str]] = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.py"):
                if not path.is_file():
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for line_number, line in enumerate(text.splitlines(), start=1):
                    match = pattern.search(line)
                    if match is None:
                        continue
                    if query.lower() not in match.group(2).lower():
                        continue
                    kind = "[class]" if match.group(1).strip() == "class" else "[symbol]"
                    matches.append((str(path), line_number, match.start(2) + 1, f"{kind} {line.strip()}"))
                    if len(matches) >= limit:
                        return matches
        return matches
