"""Lightweight in-IDE conflict resolution UI."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from tuide.models import GitConflictState
from tuide.widgets.diffview import _build_diff_markup


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
        width: 30;
        border-right: solid #21262d;
    }

    #conflict-files-title,
    #conflict-blocks-title,
    .conflict-diff-title,
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

    #conflict-blocks-panel {
        height: 9;
        border-bottom: solid #21262d;
    }

    #conflict-diff-row {
        height: 1fr;
    }

    .conflict-diff-pane {
        width: 1fr;
        border-top: solid #21262d;
    }

    .conflict-diff-scroll {
        height: 1fr;
        background: #0d1117;
    }

    .conflict-diff-content {
        background: #0d1117;
        padding: 0 1;
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

    class ApplyChoice(Message):
        """Apply a one-click resolution to the selected conflict block."""

        def __init__(self, repo_root: Path, filepath: str, block_index: int, choice: str) -> None:
            super().__init__()
            self.repo_root = repo_root
            self.filepath = filepath
            self.block_index = block_index
            self.choice = choice

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
                with Horizontal(id="conflict-diff-row"):
                    with Vertical(classes="conflict-diff-pane"):
                        yield Label("Current", id="conflict-left-title", classes="conflict-diff-title")
                        with VerticalScroll(classes="conflict-diff-scroll"):
                            yield Static("", id="conflict-left-diff", classes="conflict-diff-content")
                    with Vertical(classes="conflict-diff-pane"):
                        yield Label("Incoming", id="conflict-right-title", classes="conflict-diff-title")
                        with VerticalScroll(classes="conflict-diff-scroll"):
                            yield Static("", id="conflict-right-diff", classes="conflict-diff-content")
                yield Label("Resolved result", id="conflict-resolution-title")
                yield TextArea("", id="conflict-resolution")
                with Horizontal(id="conflict-action-row"):
                    yield Button("Accept Ours", id="conflict-ours", variant="primary")
                    yield Button("Accept Theirs", id="conflict-theirs")
                    yield Button("Accept Both", id="conflict-both")
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
        left_title = self.query_one("#conflict-left-title", Label)
        right_title = self.query_one("#conflict-right-title", Label)
        left_diff = self.query_one("#conflict-left-diff", Static)
        right_diff = self.query_one("#conflict-right-diff", Static)
        resolution = self.query_one("#conflict-resolution", TextArea)
        blocks = self.query_one("#conflict-blocks", OptionList)

        conflict_file = self._current_file()
        if conflict_file is None:
            file_label.update("No conflicted files remain. Continue to finish the operation or abort it.")
            block_label.update("")
            left_title.update("Current")
            right_title.update("Incoming")
            left_diff.update("All current conflict markers are resolved.")
            right_diff.update("")
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
                left_title.update("Current")
                right_title.update("Incoming")
                left_diff.update(
                    "This file is still marked conflicted by Git, but tuide could not parse inline markers."
                )
                right_diff.update(
                    "Open the full file, make the final contents you want, then choose Mark Resolved."
                )
                resolution.load_text("")
                self._loaded_block_key = None
                self._set_block_buttons_enabled(False)
                return

        blocks.highlighted = self._selected_block
        left_title.update(block.ours_label or "Current")
        right_title.update(block.theirs_label or "Incoming")
        left_rich, right_rich = _build_diff_markup(
            block.ours_text.splitlines(),
            block.theirs_text.splitlines(),
        )
        left_diff.update(left_rich)
        right_diff.update(right_rich)
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
            self.post_message(
                self.ApplyChoice(self._repo_root, conflict_file.filepath, block.index, "ours")
            )
            return
        if button_id == "conflict-theirs":
            resolution.load_text(block.theirs_text)
            self.post_message(
                self.ApplyChoice(self._repo_root, conflict_file.filepath, block.index, "theirs")
            )
            return
        if button_id == "conflict-both":
            combined = block.ours_text
            if block.ours_text and block.theirs_text and not block.ours_text.endswith("\n"):
                combined += "\n"
            combined += block.theirs_text
            resolution.load_text(combined)
            self.post_message(
                self.ApplyChoice(self._repo_root, conflict_file.filepath, block.index, "both")
            )
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
