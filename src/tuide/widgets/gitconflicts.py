"""Lightweight in-IDE conflict resolution UI."""

from __future__ import annotations

import shutil
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Key, Resize
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from tuide.models import GitConflictState
from tuide.widgets.diffview import render_side_by_side_diff


class ConflictCompareView(Vertical):
    """Single-scroll, full-file conflict comparison view."""

    DEFAULT_CSS = """
    ConflictCompareView {
        height: 1fr;
        border-top: solid #21262d;
    }

    #conflict-compare-header {
        height: 1;
    }

    .conflict-compare-title {
        width: 1fr;
        padding: 0 1;
        background: #161b22;
        color: #8b949e;
    }

    #conflict-compare-scroll {
        height: 1fr;
        background: #0d1117;
    }

    #conflict-compare-content {
        padding: 0 1 1 1;
        background: #0d1117;
    }
    """

    def __init__(self, *children, **kwargs) -> None:
        super().__init__(*children, **kwargs)
        self._left_title = "Ours"
        self._right_title = "Theirs"
        self._left_text = ""
        self._right_text = ""
        self._focus_line = 1

    def compose(self) -> ComposeResult:
        with Horizontal(id="conflict-compare-header"):
            yield Label("Ours", id="conflict-left-title", classes="conflict-compare-title")
            yield Label("Theirs", id="conflict-right-title", classes="conflict-compare-title")
        with VerticalScroll(id="conflict-compare-scroll"):
            yield Static("", id="conflict-compare-content")

    def on_mount(self) -> None:
        self.call_after_refresh(self._render)

    def on_resize(self, event: Resize) -> None:
        self.call_after_refresh(self._render)

    def set_diff(
        self,
        *,
        left_title: str,
        left_text: str,
        right_title: str,
        right_text: str,
        focus_line: int = 1,
    ) -> None:
        self._left_title = left_title
        self._left_text = left_text
        self._right_title = right_title
        self._right_text = right_text
        self._focus_line = focus_line
        if self.is_mounted:
            self._render()

    def _render(self) -> None:
        self.query_one("#conflict-left-title", Label).update(self._left_title)
        self.query_one("#conflict-right-title", Label).update(self._right_title)
        width = self.query_one("#conflict-compare-scroll", VerticalScroll).size.width
        width = width or self.size.width or shutil.get_terminal_size().columns
        body = render_side_by_side_diff(
            self._left_title,
            self._left_text,
            self._right_title,
            self._right_text,
            max(80, width - 2),
            full_context=True,
        )
        self.query_one("#conflict-compare-content", Static).update(body)
        self.query_one("#conflict-compare-scroll", VerticalScroll).scroll_to(
            y=max(0, self._focus_line - 3),
            animate=False,
        )


class _ConflictDismissMixin:
    """Dismiss the full-screen resolver with Escape."""

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(None)
            event.stop()


class GitConflictResolverScreen(_ConflictDismissMixin, ModalScreen[None]):
    """Full-screen overlay for conflict resolution."""

    CSS = """
    GitConflictResolverScreen {
        align: center middle;
        background: #0d1117 88%;
    }

    #conflict-screen-frame {
        width: 98%;
        height: 96%;
        border: solid #30363d;
        background: #0d1117;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Close", show=False),
    ]

    def __init__(self, state: GitConflictState, repo_root: Path) -> None:
        super().__init__()
        self._repo_root = repo_root
        self._view = GitConflictResolverView(state, repo_root)

    def compose(self) -> ComposeResult:
        with Vertical(id="conflict-screen-frame"):
            yield self._view

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def set_state(self, state: GitConflictState, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._view.set_state(state, repo_root)


class GitConflictResolverView(Vertical):
    """Resolve merge or rebase conflicts without leaving the IDE."""

    DEFAULT_CSS = """
    GitConflictResolverView {
        height: 1fr;
        background: #0d1117;
        color: #e6edf3;
    }

    #conflict-header {
        height: auto;
        padding: 0 1;
        background: #161b22;
        color: #8b949e;
    }

    #conflict-body {
        height: 1fr;
    }

    #conflict-files-panel {
        width: 24;
        border-right: solid #21262d;
    }

    #conflict-files-title,
    #conflict-blocks-title,
    #conflict-resolution-title {
        height: 1;
        padding: 0 1;
        background: #161b22;
        color: #8b949e;
    }

    #conflict-files,
    #conflict-blocks {
        height: 1fr;
        border: none;
        background: #0d1117;
    }

    #conflict-detail-panel {
        width: 1fr;
    }

    #conflict-selected-file,
    #conflict-selected-block {
        height: auto;
        padding: 0 1;
    }

    #conflict-selected-file {
        color: #79c0ff;
        background: #0d1117;
    }

    #conflict-selected-block {
        color: #8b949e;
        background: #0d1117;
    }

    #conflict-hint {
        height: auto;
        padding: 0 1;
        color: #6e7681;
        background: #0d1117;
    }

    #conflict-blocks-panel {
        height: 9;
        border-bottom: solid #21262d;
    }

    #conflict-diff-row {
        height: 1fr;
    }

    #conflict-resolution-title {
        border-top: solid #21262d;
    }

    #conflict-resolution {
        height: 10;
        background: #0d1117;
    }

    #conflict-action-row,
    #conflict-flow-row {
        height: auto;
        padding: 0 1;
        align: left middle;
        background: #161b22;
    }

    #conflict-flow-row {
        border-top: solid #21262d;
    }

    #conflict-action-row Button,
    #conflict-flow-row Button {
        margin-right: 1;
        height: 1;
        min-height: 1;
        padding: 0 2;
        border: none;
    }
    """

    class ApplyEditedResult(Message):
        """Apply custom edited resolution text to the selected block."""

        def __init__(self, repo_root: Path, filepath: str, block_index: int, text: str) -> None:
            super().__init__()
            self.repo_root = repo_root
            self.filepath = filepath
            self.block_index = block_index
            self.text = text

    class EditManually(Message):
        """Open the selected file in the editor for full-file manual resolution."""

        def __init__(self, repo_root: Path, filepath: str, start_line: int) -> None:
            super().__init__()
            self.repo_root = repo_root
            self.filepath = filepath
            self.start_line = start_line

    class MarkResolved(Message):
        """Stage the selected file after manual resolution."""

        def __init__(self, repo_root: Path, filepath: str) -> None:
            super().__init__()
            self.repo_root = repo_root
            self.filepath = filepath

    class ContinueRequested(Message):
        """Continue the in-progress merge or rebase."""

        def __init__(self, repo_root: Path) -> None:
            super().__init__()
            self.repo_root = repo_root

    class AbortRequested(Message):
        """Abort the in-progress merge or rebase."""

        def __init__(self, repo_root: Path) -> None:
            super().__init__()
            self.repo_root = repo_root

    class RefreshRequested(Message):
        """Reload current conflict state from disk and Git."""

        def __init__(self, repo_root: Path) -> None:
            super().__init__()
            self.repo_root = repo_root

    def __init__(self, state: GitConflictState, repo_root: Path) -> None:
        super().__init__()
        self._state = state
        self._repo_root = repo_root
        self._selected_file = 0 if state.files else -1
        self._selected_block = 0
        self._loaded_block_key: tuple[int, int] | None = None

    def set_state(self, state: GitConflictState, repo_root: Path) -> None:
        """Refresh the resolver with new conflict state."""
        self._state = state
        self._repo_root = repo_root
        if self._selected_file >= len(state.files):
            self._selected_file = 0 if state.files else -1
            self._selected_block = 0
        current_file = self._current_file()
        if current_file is not None and self._selected_block >= len(current_file.blocks):
            self._selected_block = 0
        self._loaded_block_key = None
        self._refresh_details()

    def compose(self) -> ComposeResult:
        count = len(self._state.files)
        yield Label(
            f" [bold #79c0ff]{self._state.operation}[/]"
            f"  [dim #8b949e]{count} conflicted file{'s' if count != 1 else ''}[/]"
            "  [dim]Resolve blocks inline, then continue or abort[/]",
            id="conflict-header",
            markup=True,
        )
        with Horizontal(id="conflict-body"):
            with Vertical(id="conflict-files-panel"):
                yield Label("Files", id="conflict-files-title")
                yield OptionList(*self._file_options(), id="conflict-files")
            with Vertical(id="conflict-detail-panel"):
                yield Static("", id="conflict-selected-file")
                with Vertical(id="conflict-blocks-panel"):
                    yield Label("Conflict blocks", id="conflict-blocks-title")
                    yield OptionList(*self._block_options(), id="conflict-blocks")
                yield Static("", id="conflict-selected-block")
                yield Static(
                    "Top panes are read-only. Edit the final resolved text below, then apply it.",
                    id="conflict-hint",
                )
                with Vertical(id="conflict-diff-row"):
                    yield ConflictCompareView(id="conflict-compare")
                yield Label("Resolved result", id="conflict-resolution-title")
                yield TextArea("", id="conflict-resolution")
                with Horizontal(id="conflict-action-row"):
                    yield Button("Use Ours", id="conflict-ours", variant="primary")
                    yield Button("Use Theirs", id="conflict-theirs")
                    yield Button("Use Both", id="conflict-both")
                    yield Button("Apply Edited Result", id="conflict-apply-edited", variant="success")
                    yield Button("Edit Full File", id="conflict-edit")
                    yield Button("Mark Resolved", id="conflict-mark", variant="success")
                with Horizontal(id="conflict-flow-row"):
                    yield Button("Refresh", id="conflict-refresh")
                    yield Button("Continue", id="conflict-continue", variant="success")
                    yield Button("Abort", id="conflict-abort", variant="error")

    def on_mount(self) -> None:
        self._refresh_details()
        try:
            files = self.query_one("#conflict-files", OptionList)
            if files.option_count:
                files.highlighted = self._selected_file
            blocks = self.query_one("#conflict-blocks", OptionList)
            if blocks.option_count:
                blocks.highlighted = self._selected_block
                self.query_one("#conflict-resolution", TextArea).focus()
            else:
                files.focus()
        except Exception:
            pass

    def _file_options(self) -> list[Option]:
        return [
            Option(
                f"{Path(conflict.filepath).name} ({len(conflict.blocks)} blocks)",
                id=f"file:{index}",
            )
            for index, conflict in enumerate(self._state.files)
        ]

    def _block_options(self) -> list[Option]:
        conflict_file = self._current_file()
        if conflict_file is None:
            return []
        return [
            Option(
                f"Block {block.index + 1}  lines {block.start_line}-{block.end_line}",
                id=f"block:{block.index}",
            )
            for block in conflict_file.blocks
        ]

    def _current_file(self):
        if self._selected_file < 0 or self._selected_file >= len(self._state.files):
            return None
        return self._state.files[self._selected_file]

    def _current_block(self):
        conflict_file = self._current_file()
        if conflict_file is None:
            return None
        if self._selected_block < 0 or self._selected_block >= len(conflict_file.blocks):
            return None
        return conflict_file.blocks[self._selected_block]

    def _refresh_details(self) -> None:
        file_label = self.query_one("#conflict-selected-file", Static)
        block_label = self.query_one("#conflict-selected-block", Static)
        compare = self.query_one("#conflict-compare", ConflictCompareView)
        resolution = self.query_one("#conflict-resolution", TextArea)
        blocks = self.query_one("#conflict-blocks", OptionList)

        conflict_file = self._current_file()
        if conflict_file is None:
            file_label.update("No conflicted files remain. Continue to finish the operation or abort it.")
            block_label.update("")
            compare.set_diff(
                left_title="Ours",
                left_text="All current conflict markers are resolved.",
                right_title="Theirs",
                right_text="",
            )
            resolution.load_text("")
            self._set_block_buttons_enabled(False)
            blocks.clear_options()
            return

        file_label.update(conflict_file.filepath)
        blocks.clear_options()
        blocks.add_options(self._block_options())

        block = self._current_block()
        if block is None:
            if conflict_file.blocks:
                self._selected_block = 0
                block = self._current_block()
            else:
                block_label.update("No inline conflict markers detected. Use full-file editing, then Mark Resolved.")
                compare.set_diff(
                    left_title="Ours",
                    left_text="This file is still marked conflicted by Git, but tuide could not parse inline markers.",
                    right_title="Theirs",
                    right_text="Open the full file, make the final contents you want, then choose Mark Resolved.",
                )
                resolution.load_text("")
                self._loaded_block_key = None
                self._set_block_buttons_enabled(False)
                return

        blocks.highlighted = self._selected_block
        ours_label = block.ours_label or "Current"
        theirs_label = block.theirs_label or "Incoming"
        compare.set_diff(
            left_title=f"Ours [{ours_label}]",
            left_text=conflict_file.ours_full_text,
            right_title=f"Theirs [{theirs_label}]",
            right_text=conflict_file.theirs_full_text,
            focus_line=min(block.ours_start_line, block.theirs_start_line),
        )
        block_label.update(
            f"Block {block.index + 1} of {len(conflict_file.blocks)}"
            f"  lines {block.start_line}-{block.end_line}"
        )

        current_key = (self._selected_file, self._selected_block)
        if self._loaded_block_key != current_key:
            resolution.load_text(block.ours_text)
            self._loaded_block_key = current_key

        self._set_block_buttons_enabled(True)

    def _set_block_buttons_enabled(self, enabled: bool) -> None:
        for button_id in (
            "#conflict-ours",
            "#conflict-theirs",
            "#conflict-both",
            "#conflict-apply-edited",
        ):
            self.query_one(button_id, Button).disabled = not enabled

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option_id or ""
        if option_id.startswith("file:"):
            self._selected_file = int(option_id.split(":", 1)[1])
            self._selected_block = 0
            self._refresh_details()
            return
        if option_id.startswith("block:"):
            self._selected_block = int(option_id.split(":", 1)[1])
            self._refresh_details()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        conflict_file = self._current_file()
        block = self._current_block()
        button_id = event.button.id

        if button_id == "conflict-refresh":
            self.post_message(self.RefreshRequested(self._repo_root))
            return
        if button_id == "conflict-continue":
            self.post_message(self.ContinueRequested(self._repo_root))
            return
        if button_id == "conflict-abort":
            self.post_message(self.AbortRequested(self._repo_root))
            return
        if conflict_file is None:
            return
        if button_id == "conflict-edit":
            start_line = block.start_line if block is not None else 1
            self.post_message(self.EditManually(self._repo_root, conflict_file.filepath, start_line))
            return
        if button_id == "conflict-mark":
            self.post_message(self.MarkResolved(self._repo_root, conflict_file.filepath))
            return
        if block is None:
            return

        resolution = self.query_one("#conflict-resolution", TextArea)

        if button_id == "conflict-ours":
            resolution.load_text(block.ours_text)
            return
        if button_id == "conflict-theirs":
            resolution.load_text(block.theirs_text)
            return
        if button_id == "conflict-both":
            combined = block.ours_text
            if block.ours_text and block.theirs_text and not block.ours_text.endswith("\n"):
                combined += "\n"
            combined += block.theirs_text
            resolution.load_text(combined)
            return
        if button_id == "conflict-apply-edited":
            self.post_message(
                self.ApplyEditedResult(
                    self._repo_root,
                    conflict_file.filepath,
                    block.index,
                    resolution.text,
                )
            )
