"""Git integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from tuide.models import GitHistoryEntry


class GitService:
    """Wrapper around Git subprocess calls."""

    def is_available(self) -> bool:
        """Return whether Git is available on PATH."""
        return shutil.which("git") is not None

    def repo_root_for(self, path: Path) -> Path | None:
        """Return the Git repository root for a file path."""
        target = path if path.is_dir() else path.parent
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=target,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        return Path(result.stdout.strip())

    def current_branch(self, repo_root: Path) -> str | None:
        """Return the current branch name."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        branch = result.stdout.strip()
        return branch or None

    def list_branches(self, repo_root: Path) -> list[str]:
        """List branches for a repository."""
        try:
            result = subprocess.run(
                ["git", "branch", "--format=%(refname:short)"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def relative_path(self, repo_root: Path, path: Path) -> str:
        """Return repo-relative POSIX path."""
        return path.relative_to(repo_root).as_posix()

    def show_file(self, repo_root: Path, ref: str, path: Path) -> str | None:
        """Show a file from a given ref."""
        rel_path = self.relative_path(repo_root, path)
        try:
            result = subprocess.run(
                ["git", "show", f"{ref}:{rel_path}"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        return result.stdout

    def file_history(self, repo_root: Path, path: Path, limit: int = 50) -> str | None:
        """Return formatted history for a file."""
        rel_path = self.relative_path(repo_root, path)
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"--max-count={limit}",
                    "--date=short",
                    "--format=%h | %ad | %an | %s",
                    "--",
                    rel_path,
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        return result.stdout.strip()

    def file_history_entries(
        self, repo_root: Path, path: Path, limit: int = 50
    ) -> list[GitHistoryEntry]:
        """Return structured history entries for a file."""
        rel_path = self.relative_path(repo_root, path)
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"--max-count={limit}",
                    "--date=short",
                    "--format=%h%x1f%ad%x1f%an%x1f%s",
                    "--",
                    rel_path,
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []
        entries: list[GitHistoryEntry] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            commit, date, author, subject = line.split("\x1f", 3)
            entries.append(
                GitHistoryEntry(commit=commit, date=date, author=author, subject=subject)
            )
        return entries

    def show_file_parent(self, repo_root: Path, commit: str, path: Path) -> str | None:
        """Show a file from the parent of a commit."""
        return self.show_file(repo_root, f"{commit}~1", path)

    def blame(self, repo_root: Path, path: Path) -> str | None:
        """Return blame output for a file."""
        rel_path = self.relative_path(repo_root, path)
        try:
            result = subprocess.run(
                ["git", "blame", "--date=short", rel_path],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        return result.stdout

    def line_history(self, repo_root: Path, path: Path, start_line: int, end_line: int) -> str | None:
        """Return Git line history for a selected range."""
        rel_path = self.relative_path(repo_root, path)
        try:
            result = subprocess.run(
                ["git", "log", "-L", f"{start_line},{end_line}:{rel_path}"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        return result.stdout
