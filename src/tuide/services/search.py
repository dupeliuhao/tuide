"""Search helpers for files and text within the workspace."""

from __future__ import annotations

from pathlib import Path


class SearchService:
    """Linux-first filesystem search helpers."""

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

    def find_files(self, roots: list[Path], query: str, limit: int = 200) -> list[Path]:
        """Return matching files across workspace roots."""
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

    def search_workspace_text(self, roots: list[Path], query: str, limit: int = 500) -> list[str]:
        """Search text across workspace roots and return formatted matches."""
        normalized = query.strip()
        if not normalized:
            return []

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
