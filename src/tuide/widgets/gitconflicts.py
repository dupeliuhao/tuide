"""Lightweight in-IDE conflict resolution UI."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from tuide.models import GitConflictState


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
    #conflict-blocks-title {
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

    #conflict-preview {
        height: 1fr;
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

    class EditManually(Message):
        """Open the selected file in the editor for manual resolution."""

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

    def compose(self) -> ComposeResult:
        count = len(self._state.files)
        yield Label(
            f" [bold #79c0ff]{self._state.operation}[/]"
            f"  [dim #8b949e]{count} conflicted file{'s' if count != 1 else ''}[/]"
            "  [dim]Resolve blocks, edit manually, then continue or abort[/]",
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
                yield TextArea("", read_only=True, id="conflict-preview")
                with Horizontal(id="conflict-action-row"):
                    yield Button("Accept Ours", id="conflict-ours", variant="primary")
                    yield Button("Accept Theirs", id="conflict-theirs")
                    yield Button("Accept Both", id="conflict-both")
                    yield Button("Edit Manually", id="conflict-edit")
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
                blocks.focus()
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
        preview = self.query_one("#conflict-preview", TextArea)
        blocks = self.query_one("#conflict-blocks", OptionList)

        conflict_file = self._current_file()
        if conflict_file is None:
            file_label.update("No conflicted files remain. Continue to finish the operation or abort it.")
            block_label.update("")
            preview.load_text("All current conflict markers are resolved.")
            self._set_block_buttons_enabled(False)
            blocks.clear_options()
            return

        file_label.update(f"{conflict_file.filepath}")
        block_options = self._block_options()
        blocks.clear_options()
        blocks.add_options(block_options)

        block = self._current_block()
        if block is None:
            if conflict_file.blocks:
                self._selected_block = 0
                block = self._current_block()
            else:
                block_label.update("No inline conflict markers detected. Use Edit Manually, then Mark Resolved.")
                preview.load_text(
                    "This file is still marked conflicted by Git, but tuide could not parse inline markers.\n\n"
                    "Open it in the editor, make the final contents you want, then choose Mark Resolved."
                )
                self._set_block_buttons_enabled(False)
                return

        blocks.highlighted = self._selected_block
        preview_text = (
            f"OURS: {block.ours_label or 'Current'}\n"
            f"{'-' * 28}\n"
            f"{block.ours_text or '(empty)'}\n\n"
            f"THEIRS: {block.theirs_label or 'Incoming'}\n"
            f"{'-' * 28}\n"
            f"{block.theirs_text or '(empty)'}"
        )
        if block.base_text:
            preview_text += f"\n\nBASE\n{'-' * 28}\n{block.base_text}"
        preview.load_text(preview_text)
        block_label.update(
            f"Block {block.index + 1} of {len(conflict_file.blocks)}"
            f"  lines {block.start_line}-{block.end_line}"
        )
        self._set_block_buttons_enabled(True)

    def _set_block_buttons_enabled(self, enabled: bool) -> None:
        for button_id in ("#conflict-ours", "#conflict-theirs", "#conflict-both"):
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
        if button_id == "conflict-ours":
            self.post_message(
                self.ApplyChoice(self._repo_root, conflict_file.filepath, block.index, "ours")
            )
        elif button_id == "conflict-theirs":
            self.post_message(
                self.ApplyChoice(self._repo_root, conflict_file.filepath, block.index, "theirs")
            )
        elif button_id == "conflict-both":
            self.post_message(
                self.ApplyChoice(self._repo_root, conflict_file.filepath, block.index, "both")
            )
