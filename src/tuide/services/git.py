"""Git integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from tuide.models import GitHistoryEntry


class GitService:
    """Wrapper around Git subprocess calls."""

    def _run(self, repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str] | None:
        """Run a Git command and return the completed process."""
        try:
            return subprocess.run(
                ["git", *args],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _run_with_error(
        self, repo_root: Path, args: list[str]
    ) -> tuple[bool, str]:
        """Run a Git command and return success plus combined output."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError:
            return False, "Git is not available on PATH."
        except subprocess.CalledProcessError as error:
            output = (error.stdout or "").strip()
            err = (error.stderr or "").strip()
            combined = "\n".join(part for part in [output, err] if part).strip()
            return False, combined or "Git command failed."
        output = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        combined = "\n".join(part for part in [output, err] if part).strip()
        return True, combined or "Git command completed."

    def is_available(self) -> bool:
        """Return whether Git is available on PATH."""
        return shutil.which("git") is not None

    def repo_root_for(self, path: Path) -> Path | None:
        """Return the Git repository root for a file path."""
        target = path if path.is_dir() else path.parent
        result = self._run(target, ["rev-parse", "--show-toplevel"])
        if result is None:
            return None
        return Path(result.stdout.strip())

    def current_branch(self, repo_root: Path) -> str | None:
        """Return the current branch name."""
        result = self._run(repo_root, ["branch", "--show-current"])
        if result is None:
            return None
        branch = result.stdout.strip()
        return branch or None

    def list_branches(self, repo_root: Path) -> list[str]:
        """List branches for a repository."""
        result = self._run(repo_root, ["branch", "--format=%(refname:short)"])
        if result is None:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def list_all_branches(self, repo_root: Path) -> list[str]:
        """List local and remote branches for a repository."""
        result = self._run(
            repo_root,
            ["branch", "--all", "--format=%(refname:short)"],
        )
        if result is None:
            return []

        branches: list[str] = []
        seen: set[str] = set()
        for raw_line in result.stdout.splitlines():
            branch = raw_line.strip()
            if not branch or "HEAD ->" in branch:
                continue
            if branch.startswith("remotes/"):
                branch = branch.removeprefix("remotes/")
            if branch in seen:
                continue
            seen.add(branch)
            branches.append(branch)
        return branches

    def relative_path(self, repo_root: Path, path: Path) -> str:
        """Return repo-relative POSIX path."""
        return path.relative_to(repo_root).as_posix()

    def show_file(self, repo_root: Path, ref: str, path: Path) -> str | None:
        """Show a file from a given ref."""
        rel_path = self.relative_path(repo_root, path)
        result = self._run(repo_root, ["show", f"{ref}:{rel_path}"])
        if result is None:
            return None
        return result.stdout

    def file_history(self, repo_root: Path, path: Path, limit: int = 50) -> str | None:
        """Return formatted history for a file."""
        rel_path = self.relative_path(repo_root, path)
        result = self._run(
            repo_root,
            [
                "log",
                f"--max-count={limit}",
                "--date=short",
                "--format=%h | %ad | %an | %s",
                "--",
                rel_path,
            ],
        )
        if result is None:
            return None
        return result.stdout.strip()

    def file_history_entries(
        self, repo_root: Path, path: Path, limit: int = 50
    ) -> list[GitHistoryEntry]:
        """Return structured history entries for a file."""
        rel_path = self.relative_path(repo_root, path)
        result = self._run(
            repo_root,
            [
                "log",
                f"--max-count={limit}",
                "--date=short",
                "--format=%h%x1f%ad%x1f%an%x1f%s",
                "--",
                rel_path,
            ],
        )
        if result is None:
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
        result = self._run(repo_root, ["blame", "--date=short", rel_path])
        if result is None:
            return None
        return result.stdout

    def line_history(self, repo_root: Path, path: Path, start_line: int, end_line: int) -> str | None:
        """Return Git line history for a selected range."""
        rel_path = self.relative_path(repo_root, path)
        result = self._run(repo_root, ["log", "-L", f"{start_line},{end_line}:{rel_path}"])
        if result is None:
            return None
        return result.stdout

    def status_summary(self, repo_root: Path) -> str | None:
        """Return a readable status summary for the repository."""
        result = self._run(
            repo_root,
            ["status", "--short", "--branch"],
        )
        if result is None:
            return None
        return result.stdout.strip() or "Working tree clean."

    def pull(self, repo_root: Path) -> tuple[bool, str]:
        """Update the current branch from its upstream."""
        return self._run_with_error(repo_root, ["pull", "--ff-only"])

    def checkout_branch(self, repo_root: Path, branch: str) -> tuple[bool, str]:
        """Switch the repository to another branch."""
        local_branches = set(self.list_branches(repo_root))
        if branch in local_branches:
            return self._run_with_error(repo_root, ["switch", branch])

        if "/" in branch and not branch.startswith("HEAD"):
            local_name = branch.split("/", 1)[1]
            if local_name in local_branches:
                return self._run_with_error(repo_root, ["switch", local_name])
            return self._run_with_error(repo_root, ["switch", "--track", "-c", local_name, branch])

        return self._run_with_error(repo_root, ["switch", branch])

    def commit_all(self, repo_root: Path, message: str) -> tuple[bool, str]:
        """Stage all tracked changes and create a commit."""
        staged_ok, staged_output = self._run_with_error(repo_root, ["add", "-u"])
        if not staged_ok:
            return False, staged_output
        commit_ok, commit_output = self._run_with_error(repo_root, ["commit", "-m", message])
        if commit_ok:
            return True, commit_output
        if "nothing to commit" in commit_output.lower():
            return False, commit_output
        return False, commit_output

    def list_changed_files(self, repo_root: Path) -> list[Path]:
        """Return paths of files changed vs HEAD (staged + unstaged)."""
        changed: set[str] = set()
        for args in (
            ["diff", "--name-only", "HEAD"],
            ["diff", "--name-only", "--cached", "HEAD"],
        ):
            result = self._run(repo_root, args)
            if result is not None:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line:
                        changed.add(line)
        return [repo_root / rel for rel in sorted(changed)]

    def branch_history(self, repo_root: Path, limit: int = 200) -> list[GitHistoryEntry]:
        """Return structured history entries for the current branch."""
        result = self._run(
            repo_root,
            [
                "log",
                f"--max-count={limit}",
                "--date=short",
                "--format=%h%x1f%ad%x1f%an%x1f%s",
            ],
        )
        if result is None:
            return []
        entries: list[GitHistoryEntry] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\x1f", 3)
            if len(parts) == 4:
                entries.append(
                    GitHistoryEntry(commit=parts[0], date=parts[1], author=parts[2], subject=parts[3])
                )
        return entries

    def files_changed_in_commit(
        self, repo_root: Path, commit: str
    ) -> list[tuple[str, str, str | None]]:
        """Return (status, new_filepath, old_filepath|None) for each file in a commit.

        old_filepath is only set for renames and copies; None otherwise.
        Paths are repo-relative POSIX strings.
        """
        result = self._run(
            repo_root,
            ["diff-tree", "--no-commit-id", "-r", "--name-status", commit],
        )
        if result is None:
            return []
        entries: list[tuple[str, str, str | None]] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if not parts:
                continue
            status = parts[0][0]  # first char: M, A, D, R, C, …
            if status in ("R", "C") and len(parts) >= 3:
                # rename/copy: old_path<tab>new_path
                entries.append((status, parts[2], parts[1]))
            elif len(parts) >= 2:
                entries.append((status, parts[1], None))
        return entries

    def push(self, repo_root: Path) -> tuple[bool, str]:
        """Push the current branch to its configured upstream."""
        return self._run_with_error(repo_root, ["push"])

    def fetch(self, repo_root: Path) -> tuple[bool, str]:
        """Fetch remote updates without merging."""
        return self._run_with_error(repo_root, ["fetch", "--all", "--prune"])
