"""Interactive git history widgets: commit log and per-commit changed-file list."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label, ListItem, ListView, Static

from tuide.models import GitHistoryEntry
from tuide.widgets.diffview import DiffView


class _HoverListView(ListView):
    """ListView that keeps the full hovered row highlighted."""

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
        if target is None:
            self.remove_class("pointer-hover")
            return
        try:
            target_index = self._nodes.index(target)
        except ValueError:
            self.remove_class("pointer-hover")
            return
        self.add_class("pointer-hover")
        if self.index != target_index:
            self.index = target_index

    def on_leave(self) -> None:
        self.remove_class("pointer-hover")


class _HistoryNavListView(_HoverListView):
    """Navigation list that can step back one layer with Escape."""

    BINDINGS = [*ListView.BINDINGS, Binding("escape", "back", "Back", show=False)]

    class BackRequested(Message):
        """Request to step back inside the branch-history workflow."""

    def action_back(self) -> None:
        self.post_message(self.BackRequested())


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
        yield _HoverListView(*items, id="git-log-list")

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
        yield _HoverListView(*items, id="git-files-list")

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


class GitHistoryBrowserView(Vertical):
    """Single-tab branch history browser: commits -> files -> diff."""

    class CloseRequested(Message):
        """Request to close the single-tab branch history workflow."""

    DEFAULT_CSS = """
    GitHistoryBrowserView {
        height: 1fr;
        background: #0d1117;
    }

    #history-header {
        height: 1;
        padding: 0 1;
        background: #161b22;
        color: #8b949e;
    }

    #history-body {
        height: 1fr;
    }

    #history-nav-panel {
        width: 30%;
        border-right: solid #21262d;
    }

    #history-diff-panel {
        width: 1fr;
    }

    #history-nav-header,
    #history-diff-header {
        height: 1;
        background: #21262d;
        color: #8b949e;
        padding: 0 1;
    }

    #history-nav-title {
        width: 1fr;
        height: 1;
        content-align: left middle;
    }

    #history-nav-back {
        width: auto;
        min-width: 0;
        height: 1;
        padding: 0 1;
        margin: 0;
        display: none;
    }

    #history-nav-list {
        height: 1fr;
        background: #0d1117;
        border: none;
        padding: 0;
    }

    #history-nav-list > ListItem {
        background: #0d1117;
        padding: 0 1;
    }

    #history-nav-list > ListItem.--highlight {
        background: #1f2d3d;
    }

    #history-nav-list.pointer-hover > ListItem.--highlight {
        background: #8a5a16;
    }

    #history-nav-list Static {
        background: transparent;
    }

    #history-diff-container {
        height: 1fr;
        background: #0d1117;
        border: none;
    }

    #history-diff-container DiffView {
        height: 1fr;
    }

    .history-empty {
        color: #6e7681;
        padding: 1;
    }
    """

    def __init__(
        self,
        branch: str,
        entries: list[GitHistoryEntry],
        repo_root: Path,
        git_service,
    ) -> None:
        super().__init__()
        self._branch = branch
        self._entries = entries
        self._repo_root = repo_root
        self._git_service = git_service
        self._mode = "commits"
        self._current_commit_index: int | None = None
        self._current_file_index: int | None = None
        self._current_files: list[tuple[str, str, str | None]] = []

    def compose(self) -> ComposeResult:
        count = len(self._entries)
        yield Label(
            f" [bold #79c0ff]{self._branch}[/]"
            f"  [dim #8b949e]{count} commit{'s' if count != 1 else ''}[/]"
            "  [dim]Enter / click to drill in • Esc to go back[/]",
            id="history-header",
            markup=True,
        )
        with Horizontal(id="history-body"):
            with Vertical(id="history-nav-panel"):
                with Horizontal(id="history-nav-header"):
                    yield Label("Commits", id="history-nav-title")
                    yield Button("Back", id="history-nav-back", classes="dismiss-button")
                yield _HistoryNavListView(id="history-nav-list")
            with Vertical(id="history-diff-panel"):
                yield Label("Select a commit, then a file to preview its diff", id="history-diff-header")
                yield Vertical(id="history-diff-container")

    def on_mount(self) -> None:
        self._show_commits()
        try:
            self.query_one("#history-nav-list", ListView).focus()
        except Exception:
            pass

    def _show_commits(self) -> None:
        self._mode = "commits"
        self._current_commit_index = None
        self._current_file_index = None
        self._current_files = []
        nav_title = self.query_one("#history-nav-title", Label)
        nav_list = self.query_one("#history-nav-list", ListView)
        back = self.query_one("#history-nav-back", Button)
        nav_title.update("Commits")
        back.display = False
        nav_list.clear()
        if not self._entries:
            nav_list.append(ListItem(Label("No commits found", classes="history-empty")))
            self._show_diff(None)
            return
        for entry in self._entries:
            nav_list.append(_CommitItem(entry.commit, entry.date, entry.author, entry.subject, entry.unpushed))
        nav_list.index = 0
        self.query_one("#history-diff-header", Label).update("Select a commit, then a file to preview its diff")
        self._show_diff(None)

    def _show_files_for_commit(self, index: int | None) -> None:
        self._mode = "files"
        self._current_commit_index = index
        nav_list = self.query_one("#history-nav-list", ListView)
        nav_title = self.query_one("#history-nav-title", Label)
        back = self.query_one("#history-nav-back", Button)
        nav_list.clear()
        self._current_files = []
        self._current_file_index = None

        if index is None or index < 0 or index >= len(self._entries):
            nav_title.update("Changed Files")
            back.display = True
            self._show_diff(None)
            return

        entry = self._entries[index]
        self._current_files = self._git_service.files_changed_in_commit(self._repo_root, entry.commit)
        nav_title.update(f"Files in {entry.commit[:8]}")
        back.display = True
        if not self._current_files:
            nav_list.append(ListItem(Label("No file changes recorded", classes="history-empty")))
            self._show_diff(None)
            return
        for status, filepath, old_filepath in self._current_files:
            nav_list.append(_ChangedFileItem(status, filepath, old_filepath))
        nav_list.index = 0
        self._show_diff(0)

    def _show_diff(self, index: int | None) -> None:
        self._current_file_index = index
        self.run_worker(self._load_diff(index), exclusive=True, group="branch-history-diff")

    async def _load_diff(self, index: int | None) -> None:
        try:
            header = self.query_one("#history-diff-header", Label)
            container = self.query_one("#history-diff-container", Vertical)
        except Exception:
            return

        await container.remove_children()

        commit_index = self._current_commit_index
        if (
            commit_index is None
            or commit_index < 0
            or commit_index >= len(self._entries)
            or index is None
            or index < 0
            or index >= len(self._current_files)
        ):
            header.update("Select a file to preview its diff")
            return

        commit = self._entries[commit_index].commit
        status, filepath, old_filepath = self._current_files[index]
        short = commit[:8]
        header.update(f"{filepath}  ({short})")

        if status == "A":
            before_text = ""
            before_label = "/dev/null"
        else:
            source = old_filepath if old_filepath else filepath
            before_raw = await asyncio.to_thread(
                lambda: self._git_service.show_file(self._repo_root, f"{commit}~1", self._repo_root / source)
            )
            before_text = before_raw if before_raw is not None else ""
            before_label = f"{short}~1:{source}"

        if status == "D":
            after_text = ""
            after_label = "/dev/null"
        else:
            after_raw = await asyncio.to_thread(
                lambda: self._git_service.show_file(self._repo_root, commit, self._repo_root / filepath)
            )
            after_text = after_raw if after_raw is not None else ""
            after_label = f"{short}:{filepath}"

        await container.mount(DiffView(before_label, before_text, after_label, after_text))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "history-nav-list":
            return
        if self._mode == "files":
            self._show_diff(event.list_view.index)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "history-nav-list":
            return
        event.stop()
        if self._mode == "commits":
            self._show_files_for_commit(event.list_view.index)
            return
        self._show_diff(event.list_view.index)

    @on(Button.Pressed, "#history-nav-back")
    def _on_back(self) -> None:
        self._show_commits()
        try:
            self.query_one("#history-nav-list", ListView).focus()
        except Exception:
            pass

    @on(_HistoryNavListView.BackRequested)
    def _on_nav_back_requested(self, _event: _HistoryNavListView.BackRequested) -> None:
        if self._mode != "files":
            self.post_message(self.CloseRequested())
            return
        self._show_commits()
        try:
            self.query_one("#history-nav-list", ListView).focus()
        except Exception:
            pass
