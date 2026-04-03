"""Interactive git history widgets: commit log and per-commit changed-file list."""

from __future__ import annotations

from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, ListItem, ListView, Static


class _CommitItem(ListItem):
    """A selectable two-line commit row."""

    def __init__(self, commit: str, date: str, author: str, subject: str, unpushed: bool = False) -> None:
        super().__init__()
        self.commit_hash = commit
        self.commit_date = date
        self.commit_author = author
        self.commit_subject = subject
        self.commit_unpushed = unpushed

    def compose(self) -> ComposeResult:
        date_s = self.commit_date[:10] if len(self.commit_date) >= 10 else self.commit_date
        unpushed_tag = "  [bold #ffb86b]unpushed[/]  " if self.commit_unpushed else ""
        yield Static(
            f"[bold #79c0ff]{self.commit_hash}[/]  "
            f"{unpushed_tag}"
            f"[dim #8b949e]{date_s}[/]  "
            f"[#e6edf3]{self.commit_subject}[/]",
            markup=True,
            classes="commit-summary",
        )
        yield Static(
            f"[dim #6e7681]{self.commit_author}[/]",
            markup=True,
            classes="commit-author",
        )

class _ChangedFileItem(ListItem):
    """A selectable changed-file row with status badge."""

    _STATUS_COLOR: dict[str, str] = {
        "M": "#e8820c",
        "A": "#89d185",
        "D": "#ff8888",
        "R": "#79c0ff",
        "C": "#8b949e",
    }

    def __init__(self, status: str, filepath: str, old_filepath: str | None) -> None:
        super().__init__()
        self.file_status = status
        self.file_path = filepath
        self.old_file_path = old_filepath

    def compose(self) -> ComposeResult:
        color = self._STATUS_COLOR.get(self.file_status, "#c9d1d9")
        if self.old_file_path is not None:
            label = f"{self.old_file_path} → {self.file_path}"
        else:
            label = self.file_path
        yield Static(
            f"[bold {color}]{self.file_status}[/]  [#e6edf3]{label}[/]",
            markup=True,
        )


class GitLogView(Vertical):
    """Interactive commit list for the current branch.

    Posts :class:`GitLogView.CommitSelected` when the user selects a commit.
    """

    class CommitSelected(Message):
        """User selected a commit from the log."""

        def __init__(self, commit: str, subject: str, repo_root: Path) -> None:
            super().__init__()
            self.commit = commit
            self.subject = subject
            self.repo_root = repo_root

    def __init__(self, branch: str, entries: list, repo_root: Path) -> None:
        super().__init__()
        self._branch = branch
        self._entries = entries
        self._repo_root = repo_root

    def compose(self) -> ComposeResult:
        n = len(self._entries)
        yield Label(
            f" [bold #79c0ff]{self._branch}[/]"
            f"  [dim #8b949e]{n} commit{'s' if n != 1 else ''}[/]"
            "  [dim]Enter / click to open[/]",
            classes="git-list-header",
            markup=True,
        )
        items = [
            _CommitItem(e.commit, e.date, e.author, e.subject, e.unpushed)
            for e in self._entries
        ]
        yield ListView(*items, id="git-log-list")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        if isinstance(event.item, _CommitItem):
            self.post_message(
                self.CommitSelected(
                    commit=event.item.commit_hash,
                    subject=event.item.commit_subject,
                    repo_root=self._repo_root,
                )
            )

    def on_mouse_move(self, event: events.MouseMove) -> None:
        target: ListItem | None = None
        try:
            widget, _ = self.screen.get_widget_at(event.screen_x, event.screen_y)
            node = widget
            while node is not None:
                if isinstance(node, ListItem):
                    target = node
                    break
                node = node.parent
        except Exception:
            pass
        for item in self.query(ListItem):
            if item is target:
                item.add_class("hovered")
            else:
                item.remove_class("hovered")

    def on_leave(self) -> None:
        for item in self.query(ListItem):
            item.remove_class("hovered")


class GitChangedFilesView(Vertical):
    """Interactive list of files changed in a single commit.

    Posts :class:`GitChangedFilesView.FileSelected` when the user picks a file.
    """

    class FileSelected(Message):
        """User selected a file from the commit's change list."""

        def __init__(
            self,
            commit: str,
            filepath: str,
            status: str,
            old_filepath: str | None,
            repo_root: Path,
        ) -> None:
            super().__init__()
            self.commit = commit
            self.filepath = filepath
            self.status = status
            self.old_filepath = old_filepath
            self.repo_root = repo_root

    def __init__(
        self,
        commit: str,
        subject: str,
        file_entries: list[tuple[str, str, str | None]],
        repo_root: Path,
    ) -> None:
        super().__init__()
        self._commit = commit
        self._subject = subject
        self._file_entries = file_entries
        self._repo_root = repo_root

    def compose(self) -> ComposeResult:
        short = self._commit[:8]
        n = len(self._file_entries)
        yield Label(
            f" [bold #79c0ff]{short}[/]  [#e6edf3]{self._subject}[/]"
            f"  [dim #8b949e]{n} file{'s' if n != 1 else ''}[/]"
            "  [dim]Enter / click to diff[/]",
            classes="git-list-header",
            markup=True,
        )
        items = [
            _ChangedFileItem(status, filepath, old_filepath)
            for status, filepath, old_filepath in self._file_entries
        ]
        yield ListView(*items, id="git-files-list")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        if isinstance(event.item, _ChangedFileItem):
            self.post_message(
                self.FileSelected(
                    commit=self._commit,
                    filepath=event.item.file_path,
                    status=event.item.file_status,
                    old_filepath=event.item.old_file_path,
                    repo_root=self._repo_root,
                )
            )

    def on_mouse_move(self, event: events.MouseMove) -> None:
        target: ListItem | None = None
        try:
            widget, _ = self.screen.get_widget_at(event.screen_x, event.screen_y)
            node = widget
            while node is not None:
                if isinstance(node, ListItem):
                    target = node
                    break
                node = node.parent
        except Exception:
            pass
        for item in self.query(ListItem):
            if item is target:
                item.add_class("hovered")
            else:
                item.remove_class("hovered")

    def on_leave(self) -> None:
        for item in self.query(ListItem):
            item.remove_class("hovered")
