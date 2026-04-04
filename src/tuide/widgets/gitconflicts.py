"""Lightweight in-IDE conflict resolution UI."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Key, MouseScrollDown, MouseScrollUp
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from tuide.models import GitConflictState
from tuide.services.git import GitService
from tuide.widgets.editor import _apply_language, build_editor_theme, detect_language


class ConflictViewer(Static):
    """Read-only code viewer used for the ours/theirs panes."""

    class WheelScrolled(Message):
        """Mouse wheel intent routed to the shared result pane."""

        def __init__(self, view_id: str, direction: int) -> None:
            super().__init__()
            self.view_id = view_id
            self.direction = direction

    def __init__(self, *, view_id: str, **kwargs) -> None:
        super().__init__("", id=view_id, **kwargs)
        try:
            self._viewer = TextArea("", read_only=True, soft_wrap=False, tab_behavior="indent")
            self._viewer.register_theme(build_editor_theme())
            self._viewer.theme = "tuide_code"
        except Exception:
            self._viewer = TextArea("", read_only=True, soft_wrap=False, tab_behavior="indent")
        self._viewer.show_line_numbers = True
        self._viewer.show_vertical_scrollbar = False
        self.can_focus = False

    def compose(self) -> ComposeResult:
        yield self._viewer

    def set_content(self, path: Path, text: str) -> None:
        """Load pane text and apply file-based syntax highlighting."""
        self._viewer.load_text(text)
        _apply_language(self._viewer, detect_language(path))

    def set_scroll_y(self, scroll_y: float) -> None:
        """Apply a mirrored vertical offset from the shared scrollbar."""
        self._viewer.scroll_to(y=max(0, scroll_y), animate=False, force=True)

    def set_cursor_line(self, line: int) -> None:
        """Place the read-only cursor near the selected conflict block."""
        try:
            self._viewer.cursor_location = (max(0, line - 1), 0)
        except Exception:
            pass

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        self.post_message(self.WheelScrolled(self.id or "", -1))
        event.stop()

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        self.post_message(self.WheelScrolled(self.id or "", 1))
        event.stop()


class ConflictResultEditor(TextArea):
    """Editable center pane whose scrolling is controlled by the shared scrollbar."""

    class WheelScrolled(Message):
        """Mouse wheel intent routed to the shared result scrollbar."""

        def __init__(self, direction: int) -> None:
            super().__init__()
            self.direction = direction

    def __init__(self, **kwargs) -> None:
        super().__init__("", soft_wrap=False, tab_behavior="indent", **kwargs)
        try:
            self.register_theme(build_editor_theme())
            self.theme = "tuide_code"
        except Exception:
            pass
        self.show_line_numbers = True
        self.show_vertical_scrollbar = False

    def set_content(self, path: Path, text: str) -> None:
        """Load full result text and apply syntax highlighting."""
        self.load_text(text)
        _apply_language(self, detect_language(path))

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        self.post_message(self.WheelScrolled(-1))
        event.stop()

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        self.post_message(self.WheelScrolled(1))
        event.stop()


class ConflictSharedScroll(VerticalScroll):
    """Single shared vertical scrollbar for the three-pane merge view."""

    DEFAULT_CSS = """
    ConflictSharedScroll {
        width: 2;
        min-width: 2;
        height: 1fr;
        background: #0d1117;
    }
    """

    class Scrolled(Message):
        """Shared scrollbar moved to a new vertical offset."""

        def __init__(self, scroll_y: float) -> None:
            super().__init__()
            self.scroll_y = scroll_y

    def compose(self) -> ComposeResult:
        yield Static(" ", id="conflict-shared-scroll-spacer")

    def set_line_count(self, line_count: int) -> None:
        """Resize the spacer so the shared scrollbar has the right range."""
        spacer = self.query_one("#conflict-shared-scroll-spacer", Static)
        spacer.update("\n".join(" " for _ in range(max(1, line_count))))

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        if round(old_value) == round(new_value) or not self.is_mounted:
            return
        self.post_message(self.Scrolled(new_value))


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
        width: 100%;
        height: 100%;
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
        width: 18;
        border-right: solid #21262d;
    }

    #conflict-files-title,
    #conflict-blocks-title,
    .conflict-pane-title {
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

    #conflict-status {
        height: auto;
        padding: 0 1;
    }

    #conflict-status {
        color: #8b949e;
        background: #0d1117;
    }

    #conflict-blocks-panel {
        height: 7;
        border-bottom: solid #21262d;
    }

    #conflict-merge-row {
        height: 1fr;
        border-top: solid #21262d;
    }

    #conflict-merge-panes {
        width: 1fr;
        height: 1fr;
    }

    .conflict-merge-pane {
        height: 1fr;
        width: 1fr;
        background: #0d1117;
    }

    #conflict-result-pane {
        width: 2fr;
        border-left: solid #21262d;
        border-right: solid #21262d;
    }

    #conflict-pane-titles {
        height: 1;
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
        """Write the edited result file back to the working tree."""

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
        self._syncing_scroll = False
        self._git_service = GitService()

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
                with Vertical(id="conflict-blocks-panel"):
                    yield Label("Conflict blocks", id="conflict-blocks-title")
                    yield OptionList(*self._block_options(), id="conflict-blocks")
                yield Static("", id="conflict-status")
                with Horizontal(id="conflict-pane-titles"):
                    yield Label("Ours", id="conflict-ours-title", classes="conflict-pane-title")
                    yield Label("Result", id="conflict-result-title", classes="conflict-pane-title")
                    yield Label("Theirs", id="conflict-theirs-title", classes="conflict-pane-title")
                with Horizontal(id="conflict-merge-row"):
                    with Horizontal(id="conflict-merge-panes"):
                        yield ConflictViewer(view_id="conflict-ours-pane", classes="conflict-merge-pane")
                        yield ConflictResultEditor(id="conflict-result-pane", classes="conflict-merge-pane")
                        yield ConflictViewer(view_id="conflict-theirs-pane", classes="conflict-merge-pane")
                    yield ConflictSharedScroll(id="conflict-shared-scroll")
                with Horizontal(id="conflict-action-row"):
                    yield Button("Prev Block", id="conflict-prev")
                    yield Button("Next Block", id="conflict-next")
                    yield Button("Use Ours", id="conflict-ours", variant="primary")
                    yield Button("Use Theirs", id="conflict-theirs")
                    yield Button("Use Both", id="conflict-both")
                    yield Button("Apply Result File", id="conflict-apply-edited", variant="success")
                    yield Button("Open Full File", id="conflict-edit")
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
                self.query_one("#conflict-result-pane", ConflictResultEditor).focus()
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
        status = self.query_one("#conflict-status", Static)
        ours_title = self.query_one("#conflict-ours-title", Label)
        result_title = self.query_one("#conflict-result-title", Label)
        theirs_title = self.query_one("#conflict-theirs-title", Label)
        ours_pane = self.query_one("#conflict-ours-pane", ConflictViewer)
        result_pane = self.query_one("#conflict-result-pane", ConflictResultEditor)
        theirs_pane = self.query_one("#conflict-theirs-pane", ConflictViewer)
        shared_scroll = self.query_one("#conflict-shared-scroll", ConflictSharedScroll)
        blocks = self.query_one("#conflict-blocks", OptionList)

        conflict_file = self._current_file()
        if conflict_file is None:
            status.update("No conflicted files remain. Continue to finish the operation or abort it.")
            ours_title.update("Ours")
            result_title.update("Result")
            theirs_title.update("Theirs")
            resolved_path = self._repo_root / "resolved.txt"
            ours_pane.set_content(resolved_path, "All current conflict markers are resolved.")
            result_pane.set_content(resolved_path, "")
            theirs_pane.set_content(resolved_path, "")
            shared_scroll.set_line_count(1)
            self._set_block_buttons_enabled(False)
            blocks.clear_options()
            return

        blocks.clear_options()
        blocks.add_options(self._block_options())
        file_path = self._repo_root / conflict_file.filepath
        current_text = self._read_worktree_text(file_path)

        block = self._current_block()
        if block is None:
            if conflict_file.blocks:
                self._selected_block = 0
                block = self._current_block()
            else:
                status.update(
                    f"{conflict_file.filepath}  No inline conflict markers detected. "
                    "Use full-file editing, then Mark Resolved."
                )
                ours_title.update("Ours")
                result_title.update("Result")
                theirs_title.update("Theirs")
                ours_pane.set_content(file_path, conflict_file.ours_full_text)
                result_pane.set_content(file_path, current_text)
                theirs_pane.set_content(file_path, conflict_file.theirs_full_text)
                shared_scroll.set_line_count(self._max_line_count(conflict_file, current_text))
                self._loaded_block_key = None
                self._set_block_buttons_enabled(False)
                return

        blocks.highlighted = self._selected_block
        ours_label = block.ours_label or "Current"
        theirs_label = block.theirs_label or "Incoming"
        ours_title.update(f"Ours [{ours_label}]")
        result_title.update("Result")
        theirs_title.update(f"Theirs [{theirs_label}]")
        ours_pane.set_content(file_path, conflict_file.ours_full_text)
        theirs_pane.set_content(file_path, conflict_file.theirs_full_text)
        shared_scroll.set_line_count(self._max_line_count(conflict_file, current_text))
        status.update(
            f"{conflict_file.filepath}  Block {block.index + 1} of {len(conflict_file.blocks)}"
            f"  lines {block.start_line}-{block.end_line}"
            "  Edit the middle Result pane, then apply the updated file."
        )

        current_key = (self._selected_file, self._selected_block)
        if self._loaded_block_key != current_key:
            result_pane.set_content(file_path, current_text)
            self._loaded_block_key = current_key
        self._align_merge_panes(
            result_line=max(1, block.start_line),
            ours_line=max(1, block.ours_start_line),
            theirs_line=max(1, block.theirs_start_line),
        )

        self._set_block_buttons_enabled(True)

    def _set_block_buttons_enabled(self, enabled: bool) -> None:
        for button_id in (
            "#conflict-prev",
            "#conflict-next",
            "#conflict-ours",
            "#conflict-theirs",
            "#conflict-both",
            "#conflict-apply-edited",
        ):
            self.query_one(button_id, Button).disabled = not enabled

        conflict_file = self._current_file()
        total = len(conflict_file.blocks) if conflict_file is not None else 0
        self.query_one("#conflict-prev", Button).disabled = not enabled or self._selected_block <= 0
        self.query_one("#conflict-next", Button).disabled = (
            not enabled or total == 0 or self._selected_block >= total - 1
        )

    def _max_line_count(self, conflict_file, result_text: str) -> int:
        """Return max line count across the three panes."""
        return max(
            1,
            len(conflict_file.ours_full_text.splitlines()) or 1,
            len(result_text.splitlines()) or 1,
            len(conflict_file.theirs_full_text.splitlines()) or 1,
        )

    def _set_pane_scroll(self, scroll_y: float) -> None:
        """Apply one shared vertical offset to all three panes."""
        ours_pane = self.query_one("#conflict-ours-pane", ConflictViewer)
        result_pane = self.query_one("#conflict-result-pane", ConflictResultEditor)
        theirs_pane = self.query_one("#conflict-theirs-pane", ConflictViewer)
        ours_pane.set_scroll_y(scroll_y)
        result_pane.scroll_to(y=max(0, scroll_y), animate=False, force=True)
        theirs_pane.set_scroll_y(scroll_y)

    def _align_merge_panes(self, *, result_line: int, ours_line: int, theirs_line: int) -> None:
        """Align the three full-file panes near the selected conflict block."""
        shared_scroll = self.query_one("#conflict-shared-scroll", ConflictSharedScroll)
        ours_pane = self.query_one("#conflict-ours-pane", ConflictViewer)
        result_pane = self.query_one("#conflict-result-pane", ConflictResultEditor)
        theirs_pane = self.query_one("#conflict-theirs-pane", ConflictViewer)
        shared_scroll_y = max(0, result_line - 3)
        shared_scroll.scroll_to(y=shared_scroll_y, animate=False, force=True)
        self._set_pane_scroll(shared_scroll_y)
        try:
            ours_pane.set_cursor_line(ours_line)
            result_pane.cursor_location = (max(0, result_line - 1), 0)
            theirs_pane.set_cursor_line(theirs_line)
        except Exception:
            pass

    def _read_worktree_text(self, path: Path) -> str:
        """Read the current working-tree text for the selected conflicted file."""
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def _replace_selected_block_text(self, replacement: str) -> str | None:
        """Return full result text with the selected conflict block replaced."""
        conflict_file = self._current_file()
        block = self._current_block()
        if conflict_file is None or block is None:
            return None
        result_pane = self.query_one("#conflict-result-pane", ConflictResultEditor)
        current_text = result_pane.text
        blocks = self._git_service.parse_conflict_blocks(current_text)
        if block.index >= len(blocks):
            return None
        current_block = blocks[block.index]
        return (
            current_text[: current_block.start_offset]
            + replacement
            + current_text[current_block.end_offset :]
        )

    def on_conflict_shared_scroll_scrolled(self, event: ConflictSharedScroll.Scrolled) -> None:
        """Mirror shared scrollbar movement across the three merge panes."""
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        try:
            self._set_pane_scroll(event.scroll_y)
        finally:
            self._syncing_scroll = False

    def on_conflict_viewer_wheel_scrolled(self, event: ConflictViewer.WheelScrolled) -> None:
        """Route wheel scrolling from read-only panes through the shared scrollbar."""
        event.stop()
        shared_scroll = self.query_one("#conflict-shared-scroll", ConflictSharedScroll)
        if event.direction < 0:
            shared_scroll.scroll_up(animate=False)
        else:
            shared_scroll.scroll_down(animate=False)

    def on_conflict_result_editor_wheel_scrolled(self, event: ConflictResultEditor.WheelScrolled) -> None:
        """Route wheel scrolling from the editable result pane through the shared scrollbar."""
        event.stop()
        shared_scroll = self.query_one("#conflict-shared-scroll", ConflictSharedScroll)
        if event.direction < 0:
            shared_scroll.scroll_up(animate=False)
        else:
            shared_scroll.scroll_down(animate=False)

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
        if button_id == "conflict-prev":
            if block is not None and self._selected_block > 0:
                self._selected_block -= 1
                self._refresh_details()
            return
        if button_id == "conflict-next":
            if conflict_file is not None and self._selected_block < len(conflict_file.blocks) - 1:
                self._selected_block += 1
                self._refresh_details()
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

        result_pane = self.query_one("#conflict-result-pane", ConflictResultEditor)

        if button_id == "conflict-ours":
            replaced = self._replace_selected_block_text(block.ours_text)
            if replaced is not None:
                result_pane.load_text(replaced)
            return
        if button_id == "conflict-theirs":
            replaced = self._replace_selected_block_text(block.theirs_text)
            if replaced is not None:
                result_pane.load_text(replaced)
            return
        if button_id == "conflict-both":
            combined = block.ours_text
            if block.ours_text and block.theirs_text and not block.ours_text.endswith("\n"):
                combined += "\n"
            combined += block.theirs_text
            replaced = self._replace_selected_block_text(combined)
            if replaced is not None:
                result_pane.load_text(replaced)
            return
        if button_id == "conflict-apply-edited":
            self.post_message(
                self.ApplyEditedResult(
                    self._repo_root,
                    conflict_file.filepath,
                    block.index,
                    result_pane.text,
                )
            )
