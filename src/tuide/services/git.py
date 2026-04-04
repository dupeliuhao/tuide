"""Git integration helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from tuide.models import (
    GitCommandResult,
    GitConflictBlock,
    GitConflictFile,
    GitConflictState,
    GitHistoryEntry,
)


class GitService:
    """Wrapper around Git subprocess calls."""

    _MERGE_BASE_MARKER = "<<<<<<< "
    _MERGE_MID_MARKER = "======="
    _MERGE_END_MARKER = ">>>>>>> "
    _MERGE_BASE_SECTION = "||||||| "

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

    # Environment that prevents git from blocking on credential prompts.
    _NO_PROMPT_ENV: dict[str, str] = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "echo",
    }

    def _run_with_error(
        self, repo_root: Path, args: list[str], *, no_prompt: bool = False
    ) -> tuple[bool, str]:
        """Run a Git command and return success plus combined output.

        Pass no_prompt=True for network operations (push/pull/fetch) so git
        never blocks waiting for credentials in a TUI context.
        """
        env = self._NO_PROMPT_ENV if no_prompt else None
        stdin = subprocess.DEVNULL if no_prompt else None
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                env=env,
                stdin=stdin,
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

    def _run_git_operation(
        self,
        repo_root: Path,
        args: list[str],
        *,
        no_prompt: bool = False,
        conflict_ok: bool = False,
    ) -> GitCommandResult:
        """Run a git command and classify divergence/conflict outcomes."""
        success, output = self._run_with_error(repo_root, args, no_prompt=no_prompt)
        if success:
            return GitCommandResult(status="success", output=output)

        lower_output = output.lower()
        if (
            "not possible to fast-forward" in lower_output
            or "divergent branches" in lower_output
            or "have diverged" in lower_output
        ):
            return GitCommandResult(status="diverged", output=output)

        if conflict_ok and self.conflict_state(repo_root) is not None:
            return GitCommandResult(status="conflict", output=output)

        return GitCommandResult(status="error", output=output)

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

    def update_current_branch(self, repo_root: Path) -> GitCommandResult:
        """Fast-forward the current branch from its upstream, without touching others."""
        result = self._run_git_operation(
            repo_root, ["pull", "--ff-only"], no_prompt=True, conflict_ok=False
        )
        if result.status != "diverged":
            return result

        guidance = (
            "Update only fast-forwards the current branch.\n"
            "This branch has diverged from upstream. Choose merge or rebase to continue."
        )
        return GitCommandResult(status="diverged", output=f"{result.output}\n\n{guidance}".strip())

    def merge_remote_changes(self, repo_root: Path) -> GitCommandResult:
        """Merge upstream into the current branch, opening a conflict flow if required."""
        return self._run_git_operation(
            repo_root,
            ["-c", "core.editor=true", "pull", "--no-rebase", "--no-edit"],
            no_prompt=True,
            conflict_ok=True,
        )

    def rebase_local_commits(self, repo_root: Path) -> GitCommandResult:
        """Rebase local commits onto upstream, opening a conflict flow if required."""
        return self._run_git_operation(
            repo_root,
            ["-c", "core.editor=true", "pull", "--rebase"],
            no_prompt=True,
            conflict_ok=True,
        )

    def merge_branch(self, repo_root: Path, branch: str) -> GitCommandResult:
        """Merge a selected local or remote branch into the current branch."""
        return self._run_git_operation(
            repo_root,
            ["-c", "core.editor=true", "merge", "--no-edit", branch],
            conflict_ok=True,
        )

    def _list_remotes(self, repo_root: Path) -> list[str]:
        """Return configured remote names."""
        result = self._run(repo_root, ["remote"])
        if result is None:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _preferred_remote(self, repo_root: Path) -> str | None:
        """Return the preferred remote name for push operations."""
        push_default = self._run(repo_root, ["config", "--get", "remote.pushDefault"])
        if push_default is not None:
            remote = push_default.stdout.strip()
            if remote:
                return remote

        remotes = self._list_remotes(repo_root)
        if "origin" in remotes:
            return "origin"
        return remotes[0] if remotes else None

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
        """Stage all changes and create a commit."""
        if self.conflict_state(repo_root) is not None:
            return False, "Resolve or abort the current merge/rebase conflict before committing."
        staged_ok, staged_output = self._run_with_error(repo_root, ["add", "-A"])
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
        unpushed = self.unpushed_commit_ids(repo_root, limit=limit)
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
                    GitHistoryEntry(
                        commit=parts[0],
                        date=parts[1],
                        author=parts[2],
                        subject=parts[3],
                        unpushed=parts[0] in unpushed,
                    )
                )
        return entries

    def push_preview_entries(self, repo_root: Path, limit: int = 200) -> list[GitHistoryEntry]:
        """Return commits that are about to be pushed for the current branch."""
        upstream = self._upstream_ref(repo_root)
        log_args = [
            "log",
            f"--max-count={limit}",
            "--date=short",
            "--format=%h%x1f%ad%x1f%an%x1f%s",
        ]
        if upstream is not None:
            log_args.append(f"{upstream}..HEAD")
        else:
            log_args.append("HEAD")

        result = self._run(repo_root, log_args)
        if result is None:
            return []

        entries: list[GitHistoryEntry] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\x1f", 3)
            if len(parts) == 4:
                entries.append(
                    GitHistoryEntry(
                        commit=parts[0],
                        date=parts[1],
                        author=parts[2],
                        subject=parts[3],
                        unpushed=True,
                    )
                )
        return entries

    def _upstream_ref(self, repo_root: Path) -> str | None:
        """Return the current branch upstream ref when one can be resolved."""
        result = self._run(
            repo_root,
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        )
        if result is not None:
            upstream = result.stdout.strip()
            if upstream:
                return upstream

        branch = self.current_branch(repo_root)
        remote = self._preferred_remote(repo_root)
        if not branch or not remote:
            return None

        candidate = f"refs/remotes/{remote}/{branch}"
        if self._run(repo_root, ["show-ref", "--verify", candidate]) is None:
            return None
        return f"{remote}/{branch}"

    def upstream_ref(self, repo_root: Path) -> str | None:
        """Return the public upstream ref for the current branch."""
        return self._upstream_ref(repo_root)

    def unpushed_commit_ids(self, repo_root: Path, limit: int = 200) -> set[str]:
        """Return abbreviated commit ids reachable from HEAD but not upstream."""
        upstream = self._upstream_ref(repo_root)
        if upstream is None:
            return set()

        result = self._run(
            repo_root,
            ["rev-list", f"--max-count={limit}", "--abbrev-commit", f"{upstream}..HEAD"],
        )
        if result is None:
            return set()
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}

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

    def status_porcelain(self, repo_root: Path) -> list[tuple[str, str]]:
        """Return (XY_status, filepath) pairs for all changed files."""
        # Use NUL-delimited porcelain to avoid quote-escaping issues on paths with spaces.
        result = self._run(repo_root, ["status", "--porcelain", "-z"])
        if result is None:
            return []

        files: list[tuple[str, str]] = []
        records = result.stdout.split("\0")
        index = 0
        while index < len(records):
            record = records[index]
            if not record or len(record) < 3:
                index += 1
                continue
            xy = record[:2]
            filepath = record[3:]
            files.append((xy, filepath))
            # Rename/copy in -z mode stores an extra NUL-delimited source path.
            if ("R" in xy or "C" in xy) and index + 1 < len(records):
                index += 2
            else:
                index += 1
        return files

    def file_diff_workdir(self, repo_root: Path, filepath: str) -> str:
        """Return unified diff of a file vs HEAD (staged + unstaged)."""
        result = self._run(repo_root, ["diff", "HEAD", "--", filepath])
        if result is not None and result.stdout.strip():
            return result.stdout
        # For untracked or fully-staged new files, fall back to cached diff
        result = self._run(repo_root, ["diff", "--cached", "HEAD", "--", filepath])
        if result is not None and result.stdout.strip():
            return result.stdout
        # Last resort: show raw file content as additions
        full_path = repo_root / filepath
        if full_path.exists():
            try:
                lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
                return "\n".join(f"+{line}" for line in lines)
            except Exception:
                pass
        return "(No diff available)"

    def restore_file(self, repo_root: Path, filepath: str) -> tuple[bool, str]:
        """Discard working-tree changes for one file, restoring to HEAD."""
        return self._run_with_error(repo_root, ["checkout", "HEAD", "--", filepath])

    def conflict_state(self, repo_root: Path) -> GitConflictState | None:
        """Return merge/rebase conflict state when the repository is mid-operation."""
        operation = self._current_conflict_operation(repo_root)
        if operation is None:
            return None

        files: list[GitConflictFile] = []
        for filepath in self.conflicted_files(repo_root):
            full_path = repo_root / filepath
            try:
                text = full_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            files.append(self._build_conflict_file(filepath, text))
        return GitConflictState(operation=operation, files=files)

    def _build_conflict_file(self, filepath: str, text: str) -> GitConflictFile:
        """Build enriched conflict state for one file, including full-file candidates."""
        blocks = self.parse_conflict_blocks(text)
        if not blocks:
            return GitConflictFile(
                filepath=filepath,
                blocks=[],
                ours_full_text=text,
                theirs_full_text=text,
            )

        ours_parts: list[str] = []
        theirs_parts: list[str] = []
        ours_line = 1
        theirs_line = 1
        cursor = 0
        enriched_blocks: list[GitConflictBlock] = []

        for block in blocks:
            prefix = text[cursor : block.start_offset]
            ours_parts.append(prefix)
            theirs_parts.append(prefix)
            ours_line += prefix.count("\n")
            theirs_line += prefix.count("\n")

            ours_start_line, ours_end_line = self._candidate_line_range(ours_line, block.ours_text)
            theirs_start_line, theirs_end_line = self._candidate_line_range(theirs_line, block.theirs_text)

            ours_parts.append(block.ours_text)
            theirs_parts.append(block.theirs_text)
            ours_line += block.ours_text.count("\n")
            theirs_line += block.theirs_text.count("\n")
            cursor = block.end_offset

            enriched_blocks.append(
                GitConflictBlock(
                    index=block.index,
                    start_line=block.start_line,
                    end_line=block.end_line,
                    start_offset=block.start_offset,
                    end_offset=block.end_offset,
                    ours_label=block.ours_label,
                    theirs_label=block.theirs_label,
                    ours_text=block.ours_text,
                    theirs_text=block.theirs_text,
                    base_text=block.base_text,
                    ours_start_line=ours_start_line,
                    ours_end_line=ours_end_line,
                    theirs_start_line=theirs_start_line,
                    theirs_end_line=theirs_end_line,
                )
            )

        suffix = text[cursor:]
        ours_parts.append(suffix)
        theirs_parts.append(suffix)
        return GitConflictFile(
            filepath=filepath,
            blocks=enriched_blocks,
            ours_full_text="".join(ours_parts),
            theirs_full_text="".join(theirs_parts),
        )

    @staticmethod
    def _candidate_line_range(current_line: int, piece: str) -> tuple[int, int]:
        """Return the inclusive line range occupied by one candidate block."""
        if not piece:
            return current_line, current_line
        occupied_lines = piece.count("\n") + (0 if piece.endswith("\n") else 1)
        end_line = current_line + max(occupied_lines - 1, 0)
        return current_line, end_line

    def conflicted_files(self, repo_root: Path) -> list[str]:
        """Return repo-relative files with unresolved merge conflicts."""
        result = self._run(repo_root, ["diff", "--name-only", "--diff-filter=U"])
        if result is None:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _current_conflict_operation(self, repo_root: Path) -> str | None:
        """Return the current conflict operation type."""
        git_dir = repo_root / ".git"
        merge_head = git_dir / "MERGE_HEAD"
        rebase_merge = git_dir / "rebase-merge"
        rebase_apply = git_dir / "rebase-apply"
        rebase_head = git_dir / "REBASE_HEAD"
        if merge_head.exists():
            return "merge"
        if rebase_head.exists() or rebase_merge.exists() or rebase_apply.exists():
            return "rebase"
        return None

    def continue_conflict_operation(self, repo_root: Path) -> GitCommandResult:
        """Continue the in-progress merge or rebase after conflicts are resolved."""
        operation = self._current_conflict_operation(repo_root)
        if operation is None:
            return GitCommandResult(status="error", output="No merge or rebase is in progress.")

        if self.conflicted_files(repo_root):
            return GitCommandResult(
                status="error",
                output="Resolve all conflicted files before continuing.",
            )

        if operation == "merge":
            return self._run_git_operation(
                repo_root,
                ["-c", "core.editor=true", "merge", "--continue"],
                conflict_ok=True,
            )
        return self._run_git_operation(
            repo_root,
            ["-c", "core.editor=true", "rebase", "--continue"],
            conflict_ok=True,
        )

    def abort_conflict_operation(self, repo_root: Path) -> GitCommandResult:
        """Abort the in-progress merge or rebase."""
        operation = self._current_conflict_operation(repo_root)
        if operation is None:
            return GitCommandResult(status="error", output="No merge or rebase is in progress.")

        if operation == "merge":
            return self._run_git_operation(repo_root, ["merge", "--abort"], conflict_ok=False)
        return self._run_git_operation(repo_root, ["rebase", "--abort"], conflict_ok=False)

    def mark_conflict_resolved(self, repo_root: Path, filepath: str) -> tuple[bool, str]:
        """Stage a conflicted file after markers are removed."""
        full_path = repo_root / filepath
        try:
            text = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            return False, str(error)

        if self.parse_conflict_blocks(text):
            return False, "Conflict markers remain in the file. Resolve them before marking resolved."

        return self._run_with_error(repo_root, ["add", "--", filepath])

    def write_worktree_file(self, repo_root: Path, filepath: str, text: str) -> tuple[bool, str]:
        """Write resolved text into the working tree without staging it."""
        full_path = repo_root / filepath
        try:
            full_path.write_text(text, encoding="utf-8")
        except OSError as error:
            return False, str(error)
        return True, f"Updated {filepath} in the working tree."

    def apply_conflict_choice(
        self, repo_root: Path, filepath: str, block_index: int, choice: str
    ) -> tuple[bool, str]:
        """Apply a resolution choice to one conflict block in a file."""
        full_path = repo_root / filepath
        try:
            text = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            return False, str(error)

        blocks = self.parse_conflict_blocks(text)
        block = next((candidate for candidate in blocks if candidate.index == block_index), None)
        if block is None:
            return False, "Unable to locate the selected conflict block."

        replacement = self._conflict_choice_text(block, choice)
        if replacement is None:
            return False, f"Unknown conflict choice: {choice}"

        updated = text[: block.start_offset] + replacement + text[block.end_offset :]
        try:
            full_path.write_text(updated, encoding="utf-8")
        except OSError as error:
            return False, str(error)
        return True, f"Applied {choice} to {Path(filepath).name}."

    def apply_conflict_resolution_text(
        self,
        repo_root: Path,
        filepath: str,
        block_index: int,
        resolved_text: str,
    ) -> tuple[bool, str]:
        """Replace one conflict block with custom resolved text."""
        full_path = repo_root / filepath
        try:
            text = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            return False, str(error)

        blocks = self.parse_conflict_blocks(text)
        block = next((candidate for candidate in blocks if candidate.index == block_index), None)
        if block is None:
            return False, "Unable to locate the selected conflict block."

        updated = text[: block.start_offset] + resolved_text + text[block.end_offset :]
        try:
            full_path.write_text(updated, encoding="utf-8")
        except OSError as error:
            return False, str(error)
        return True, f"Applied edited resolution to {Path(filepath).name}."

    def parse_conflict_blocks(self, text: str) -> list[GitConflictBlock]:
        """Parse merge conflict markers from a text file."""
        if self._MERGE_BASE_MARKER not in text:
            return []

        lines = text.splitlines(keepends=True)
        blocks: list[GitConflictBlock] = []
        line_no = 1
        offset = 0
        index = 0
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.startswith(self._MERGE_BASE_MARKER):
                offset += len(line)
                line_no += 1
                i += 1
                continue

            start_line = line_no
            start_offset = offset
            ours_label = line[len(self._MERGE_BASE_MARKER) :].rstrip("\n")
            i += 1
            line_no += 1
            offset += len(line)

            ours_lines: list[str] = []
            base_lines: list[str] = []
            theirs_lines: list[str] = []

            while i < len(lines) and not (
                lines[i].startswith(self._MERGE_BASE_SECTION) or lines[i].startswith(self._MERGE_MID_MARKER)
            ):
                ours_lines.append(lines[i])
                offset += len(lines[i])
                line_no += 1
                i += 1

            if i < len(lines) and lines[i].startswith(self._MERGE_BASE_SECTION):
                base_marker = lines[i]
                i += 1
                line_no += 1
                offset += len(base_marker)
                while i < len(lines) and not lines[i].startswith(self._MERGE_MID_MARKER):
                    base_lines.append(lines[i])
                    offset += len(lines[i])
                    line_no += 1
                    i += 1

            if i >= len(lines) or not lines[i].startswith(self._MERGE_MID_MARKER):
                break

            divider = lines[i]
            i += 1
            line_no += 1
            offset += len(divider)

            while i < len(lines) and not lines[i].startswith(self._MERGE_END_MARKER):
                theirs_lines.append(lines[i])
                offset += len(lines[i])
                line_no += 1
                i += 1

            if i >= len(lines) or not lines[i].startswith(self._MERGE_END_MARKER):
                break

            end_marker = lines[i]
            theirs_label = end_marker[len(self._MERGE_END_MARKER) :].rstrip("\n")
            i += 1
            end_offset = offset + len(end_marker)
            end_line = line_no
            line_no += 1
            offset = end_offset

            blocks.append(
                GitConflictBlock(
                    index=index,
                    start_line=start_line,
                    end_line=end_line,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    ours_label=ours_label or "Current",
                    theirs_label=theirs_label or "Incoming",
                    ours_text="".join(ours_lines),
                    theirs_text="".join(theirs_lines),
                    base_text="".join(base_lines),
                )
            )
            index += 1
        return blocks

    @staticmethod
    def _conflict_choice_text(block: GitConflictBlock, choice: str) -> str | None:
        """Return replacement text for a conflict-resolution choice."""
        normalized = choice.lower()
        if normalized == "ours":
            return block.ours_text
        if normalized == "theirs":
            return block.theirs_text
        if normalized == "both":
            pieces = [block.ours_text]
            if block.ours_text and block.theirs_text and not block.ours_text.endswith("\n"):
                pieces.append("\n")
            pieces.append(block.theirs_text)
            return "".join(pieces)
        return None

    def push(self, repo_root: Path) -> tuple[bool, str]:
        """Push the current branch to its configured upstream."""
        success, output = self._run_with_error(repo_root, ["push"], no_prompt=True)
        if success:
            return True, output

        branch = self.current_branch(repo_root)
        remote = self._preferred_remote(repo_root)
        lower_output = output.lower()
        if (
            branch
            and remote
            and ("has no upstream branch" in lower_output or "no upstream branch" in lower_output)
        ):
            return self._run_with_error(
                repo_root,
                ["push", "--set-upstream", remote, branch],
                no_prompt=True,
            )

        return False, output

    def fetch(self, repo_root: Path) -> tuple[bool, str]:
        """Fetch remote updates without merging."""
        return self._run_with_error(repo_root, ["fetch", "--all", "--prune"], no_prompt=True)
