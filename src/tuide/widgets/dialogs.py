"""Modal dialogs for tuide."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual import events
from textual.events import Key
from textual.geometry import Spacing
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, OptionList, Static
from textual.widgets.option_list import Option

from tuide.models import ChoiceItem, CommandItem, GitHistoryEntry
from tuide.widgets.diffview import DiffView


class EscapeDismissMixin:
    """Mixin that makes Escape dismiss the active modal."""

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(None)
            event.stop()


class PointerTrackingOptionList(OptionList):
    """OptionList that moves the highlighted row with pointer hover."""

    def __init__(self, *content, track_pointer: bool = True, **kwargs) -> None:
        super().__init__(*content, **kwargs)
        self.track_pointer = track_pointer

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self.track_pointer:
            return
        option_index = event.style.meta.get("option")
        if option_index is not None and option_index != self.highlighted:
            self.highlighted = option_index


class NeutralFocusDialog(Vertical):
    """Focusable dialog container that keeps button styles neutral by default."""

    can_focus = True


class ConfirmDialog(EscapeDismissMixin, ModalScreen[bool | None]):
    """A simple confirm / cancel dialog."""

    CSS = """
    ConfirmDialog {
        align: center middle;
    }

    #confirm-dialog {
        width: 56;
        height: auto;
        border: solid #30363d;
        background: #161b22;
        padding: 0 1;
    }

    #confirm-title {
        text-style: bold;
        color: #e6edf3;
        padding-bottom: 0;
    }

    #confirm-message {
        color: #8b949e;
        padding-bottom: 0;
    }

    #confirm-hint {
        color: #6e7681;
        padding-bottom: 0;
    }

    #confirm-actions {
        width: 100%;
        height: auto;
        align: right middle;
    }

    #confirm-actions Button {
        margin-left: 1;
    }

    Button {
        height: 1;
        min-height: 1;
        padding: 0 2;
        border: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Confirm", show=False),
    ]

    def __init__(
        self,
        title: str,
        message: str,
        *,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        confirm_variant: str = "warning",
        confirm_classes: str = "",
    ) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label
        self._confirm_variant = confirm_variant
        self._confirm_classes = confirm_classes

    def compose(self) -> ComposeResult:
        with NeutralFocusDialog(id="confirm-dialog"):
            yield Label(self._title, id="confirm-title")
            yield Label(self._message, id="confirm-message")
            yield Label("Esc or Back to return", id="confirm-hint")
            with Horizontal(id="confirm-actions"):
                yield Button("Back", id="confirm-cancel", classes="dismiss-button")
                yield Button(
                    self._confirm_label,
                    variant=self._confirm_variant,
                    id="confirm-ok",
                    classes=self._confirm_classes,
                )

    def on_mount(self) -> None:
        """Keep the dialog neutral until the user hovers or tabs into a button."""
        self.query_one("#confirm-dialog", NeutralFocusDialog).focus()

    def action_cancel(self) -> None:
        """Dismiss without confirming."""
        self.dismiss(None)

    def action_confirm(self) -> None:
        """Dismiss with confirmation."""
        self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        event.stop()
        if event.button.id == "confirm-ok":
            self.dismiss(True)
            return
        self.dismiss(None)


class HelpDialog(EscapeDismissMixin, ModalScreen[None]):
    """A lightweight keybinding help overlay."""

    CSS = """
    HelpDialog {
        align: center middle;
    }

    #help-dialog {
        width: 68;
        height: auto;
        max-height: 90%;
        border: solid #30363d;
        background: #161b22;
        padding: 0 1;
    }

    #help-title {
        text-style: bold;
        color: #e6edf3;
        padding-bottom: 0;
    }

    .help-line {
        color: #8b949e;
    }

    #help-close {
        margin-top: 0;
        width: 10;
        align-horizontal: right;
    }

    Button {
        height: 1;
        min-height: 1;
        padding: 0 2;
        border: none;
    }
    """

    BINDINGS = [
        Binding("escape", "close_help", "Close", show=False),
        Binding("enter", "close_help", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with NeutralFocusDialog(id="help-dialog"):
            yield Label("tuide keybindings", id="help-title")
            yield Label("Tab / Shift+Tab  cycle focus between panels", classes="help-line")
            yield Label("Esc              return focus to the editor", classes="help-line")
            yield Label("Ctrl+Z           undo last edit", classes="help-line")
            yield Label("Ctrl+Shift+Z     redo last undone edit", classes="help-line")
            yield Label("Ctrl+W           close active tab", classes="help-line")
            yield Label("Ctrl+Q           confirm before quitting tuide", classes="help-line")
            yield Label("Ctrl+B           toggle workspace panel", classes="help-line")
            yield Label("Ctrl+J           toggle terminal panel", classes="help-line")
            yield Label("Ctrl+R           restart terminal", classes="help-line")
            yield Label("?                show this help", classes="help-line")
            yield Button("Close", id="help-close", classes="dismiss-button")

    def on_mount(self) -> None:
        """Keep the close button visually neutral until the user interacts."""
        self.query_one("#help-dialog", NeutralFocusDialog).focus()

    def action_close_help(self) -> None:
        """Dismiss the help overlay."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss on button press."""
        event.stop()
        if event.button.id == "help-close":
            self.dismiss(None)


class PromptDialog(EscapeDismissMixin, ModalScreen[str | None]):
    """Prompt for a single text value."""

    CSS = """
    PromptDialog {
        align: center middle;
    }

    #prompt-dialog {
        width: 64;
        height: auto;
        border: solid #30363d;
        background: #161b22;
        padding: 0 1;
    }

    #prompt-title {
        text-style: bold;
        color: #e6edf3;
        padding-bottom: 0;
    }

    #prompt-input {
        margin-bottom: 0;
    }

    #prompt-hint {
        color: #6e7681;
        padding-bottom: 0;
    }

    #prompt-actions {
        width: 100%;
        height: auto;
        align: right middle;
    }

    Button {
        height: 1;
        min-height: 1;
        padding: 0 2;
        border: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "submit", "Submit", show=False),
    ]

    def __init__(self, title: str, placeholder: str = "", value: str = "") -> None:
        super().__init__()
        self._title = title
        self._placeholder = placeholder
        self._value = value

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-dialog"):
            yield Label(self._title, id="prompt-title")
            yield Input(value=self._value, placeholder=self._placeholder, id="prompt-input")
            yield Label("Enter to confirm, Esc or Back to return", id="prompt-hint")
            with Horizontal(id="prompt-actions"):
                yield Button("Back", id="prompt-cancel", classes="dismiss-button")
                yield Button("OK", variant="success", id="prompt-ok")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss(self.query_one("#prompt-input", Input).value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "prompt-ok":
            self.dismiss(self.query_one("#prompt-input", Input).value)
            return
        self.dismiss(None)


class CommandPaletteDialog(EscapeDismissMixin, ModalScreen[str | None]):
    """Searchable command palette."""

    CSS = """
    CommandPaletteDialog {
        align: center middle;
    }

    #palette-dialog {
        width: 76;
        height: 20;
        border: solid #30363d;
        background: #161b22;
        padding: 0 1;
    }

    #palette-title {
        text-style: bold;
        color: #e6edf3;
        padding-bottom: 0;
    }

    #palette-input {
        margin-bottom: 0;
    }

    #palette-options {
        height: 1fr;
    }

    #palette-actions {
        width: 100%;
        height: auto;
        align: right middle;
        margin-top: 0;
    }

    Button {
        height: 1;
        min-height: 1;
        padding: 0 2;
        border: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, commands: list[CommandItem]) -> None:
        super().__init__()
        self._commands = commands

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-dialog"):
            yield Label("Command palette", id="palette-title")
            yield Input(placeholder="Type to filter commands", id="palette-input")
            options = [Option(f"{item.label} — {item.description}", id=item.id) for item in self._commands]
            yield PointerTrackingOptionList(*options, id="palette-options")
            with Horizontal(id="palette-actions"):
                yield Button("Back", id="palette-cancel", classes="dismiss-button")

    def on_mount(self) -> None:
        self.query_one("#palette-input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "palette-cancel":
            self.dismiss(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter options as the input changes."""
        if event.input.id != "palette-input":
            return

        query = event.value.strip().lower()
        options = [
            Option(f"{item.label} — {item.description}", id=item.id)
            for item in self._commands
            if not query
            or query in item.label.lower()
            or query in item.description.lower()
            or query in item.id.lower()
        ]
        option_list = self.query_one("#palette-options", PointerTrackingOptionList)
        option_list.clear_options()
        option_list.add_options(options)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Dismiss with the selected command identifier."""
        self.dismiss(event.option_id)


class OptionPickerDialog(EscapeDismissMixin, ModalScreen[str | None]):
    """Pick from a list of options with lightweight filtering."""

    CSS = """
    OptionPickerDialog {
        align: center middle;
    }

    #picker-dialog {
        width: 80;
        height: 24;
        border: solid #30363d;
        background: #161b22;
        padding: 0 1;
    }

    #picker-title {
        text-style: bold;
        color: #e6edf3;
        height: 1;
    }

    #picker-input {
        height: 3;
        margin: 0;
    }

    #picker-options {
        height: 1fr;
        border: none;
        background: #161b22;
        padding: 0;
    }

    #picker-options > .option-list--option-highlighted {
        background: #8a5a16;
        color: #fff7e6;
        text-style: bold;
    }

    #picker-options:focus > .option-list--option-highlighted {
        background: #8a5a16;
        color: #fff7e6;
    }

    #picker-actions {
        width: 100%;
        height: 1;
        align: right middle;
    }

    Button {
        height: 1;
        min-height: 1;
        padding: 0 2;
        border: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        title: str,
        options: list[ChoiceItem],
        placeholder: str = "Type to filter",
        *,
        confirm_label: str | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        self._options = options
        self._placeholder = placeholder
        self._confirm_label = confirm_label
        self._pending_selection: str | None = None
        self._suspend_filtering = False

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-dialog"):
            yield Label(self._title, id="picker-title")
            yield Input(placeholder=self._placeholder, id="picker-input")
            options = [Option(self._format_option(item), id=item.id) for item in self._options]
            yield PointerTrackingOptionList(
                *options,
                id="picker-options",
                track_pointer=self._confirm_label is None,
            )
            with Horizontal(id="picker-actions"):
                yield Button("Back", id="picker-cancel", classes="dismiss-button")
                if self._confirm_label is not None:
                    yield Button(self._confirm_label, id="picker-confirm", variant="success", disabled=True)

    def on_mount(self) -> None:
        self.query_one("#picker-input", Input).focus()
        option_list = self.query_one("#picker-options", PointerTrackingOptionList)
        if option_list.option_count and self._confirm_label is None:
            option_list.highlighted = 0

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "picker-cancel":
            self.dismiss(None)
            return
        if event.button.id == "picker-confirm" and self._pending_selection is not None:
            self.dismiss(self._pending_selection)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "picker-input":
            return
        if self._suspend_filtering:
            self._suspend_filtering = False
            return
        query = event.value.strip().lower()
        option_list = self.query_one("#picker-options", PointerTrackingOptionList)
        options = [
            Option(self._format_option(item), id=item.id)
            for item in self._options
            if not query
            or query in item.id.lower()
            or query in item.label.lower()
            or query in item.description.lower()
        ]
        option_list.clear_options()
        option_list.add_options(options)
        if self._confirm_label is None:
            if option_list.option_count:
                option_list.highlighted = 0
        else:
            option_list.track_pointer = True
            self._pending_selection = None
            try:
                self.query_one("#picker-confirm", Button).disabled = True
            except Exception:
                pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if self._confirm_label is None:
            self.dismiss(event.option_id)
            return
        self._pending_selection = event.option_id
        option_list = self.query_one("#picker-options", PointerTrackingOptionList)
        option_list.track_pointer = False
        self._suspend_filtering = True
        self.query_one("#picker-input", Input).value = event.option_id
        self.query_one("#picker-confirm", Button).disabled = False

    @staticmethod
    def _format_option(item: ChoiceItem) -> str:
        if item.description:
            return f"{item.label} - {item.description}"
        return item.label


class BranchPickerScreen(EscapeDismissMixin, ModalScreen[str | None]):
    """Bottom-right branch picker popup."""

    CSS = """
    BranchPickerScreen {
        align: right bottom;
        background: #0d1117 50%;
    }

    #branch-picker {
        width: 68;
        height: auto;
        max-height: 24;
        border: solid #30363d;
        background: #161b22;
        margin-bottom: 1;
        margin-right: 0;
    }

    #branch-picker-title {
        color: #6e7681;
        height: 1;
        padding: 0 1;
        background: #0d1117;
    }

    #branch-filter {
        height: 1;
        margin: 0;
    }

    #branch-list {
        height: auto;
        max-height: 20;
        border: none;
        background: #161b22;
    }
    """

    def __init__(self, branches: list[str], current: str) -> None:
        super().__init__()
        self._branches = branches
        self._current = current
        self._visible_branches = branches[:]

    def compose(self) -> ComposeResult:
        with Vertical(id="branch-picker"):
            yield Label("switch branch", id="branch-picker-title")
            yield Input(placeholder="Filter branches", id="branch-filter")
            yield PointerTrackingOptionList(*self._branch_options(self._visible_branches), id="branch-list")

    def on_mount(self) -> None:
        self.query_one("#branch-filter", Input).focus()
        ol = self.query_one("#branch-list", PointerTrackingOptionList)
        self._highlight_current_branch(ol)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option_id)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "branch-filter":
            return
        query = event.value.strip().lower()
        self._visible_branches = [
            branch
            for branch in self._branches
            if not query or query in branch.lower()
        ]
        option_list = self.query_one("#branch-list", PointerTrackingOptionList)
        option_list.clear_options()
        option_list.add_options(self._branch_options(self._visible_branches))
        self._highlight_current_branch(option_list)

    def _branch_options(self, branches: list[str]) -> list[Option]:
        return [
            Option(("* " if branch == self._current else "  ") + branch, id=branch)
            for branch in branches
        ]

    def _highlight_current_branch(self, option_list: PointerTrackingOptionList) -> None:
        if not self._visible_branches:
            return
        try:
            option_list.highlighted = self._visible_branches.index(self._current)
        except ValueError:
            option_list.highlighted = 0


class ContextMenuScreen(EscapeDismissMixin, ModalScreen[str | None]):
    """Right-click context menu positioned at cursor coordinates."""

    CSS = """
    ContextMenuScreen {
        background: #0d1117 0%;
    }

    #context-menu {
        width: 38;
        height: auto;
        border: solid #30363d;
        background: #161b22;
    }

    #context-menu-list {
        height: auto;
        max-height: 20;
        border: none;
    }
    """

    def __init__(self, items: list[ChoiceItem], x: int, y: int) -> None:
        super().__init__()
        self._items = items
        self._x = x
        self._y = y

    def compose(self) -> ComposeResult:
        with Vertical(id="context-menu"):
            yield PointerTrackingOptionList(
                *[Option(item.label, id=item.id) for item in self._items],
                id="context-menu-list",
            )

    def on_mount(self) -> None:
        self.call_after_refresh(self._position_menu)
        self.query_one("#context-menu-list", PointerTrackingOptionList).focus()

    def _position_menu(self) -> None:
        sw, sh = self.app.size
        menu_w, menu_h = 38, len(self._items) + 2
        x = min(self._x, max(0, sw - menu_w - 1))
        y = min(self._y, max(0, sh - menu_h - 1))
        menu = self.query_one("#context-menu")
        menu.styles.margin = Spacing(y, 0, 0, x)

    def on_mouse_up(self, event) -> None:
        """Dismiss when clicking outside the menu box."""
        menu = self.query_one("#context-menu")
        if not menu.region.contains(event.screen_x, event.screen_y):
            self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option_id)


class FindReferencesScreen(EscapeDismissMixin, ModalScreen[tuple[str, int, int] | None]):
    """Bottom-right popup showing symbol-location results.

    Returns ``(path_str, line_number, column_number)`` when the user selects an entry, or
    ``None`` when dismissed.
    """

    CSS = """
    FindReferencesScreen {
        align: right bottom;
        background: #0d1117 50%;
    }

    #refs-panel {
        width: 70;
        height: auto;
        max-height: 22;
        border: solid #388bfd;
        background: #161b22;
        margin-bottom: 1;
        margin-right: 0;
        padding: 0;
    }

    #refs-title {
        color: #79c0ff;
        height: 1;
        padding: 0 1;
        background: #0d1117;
    }

    #refs-empty {
        color: #8b949e;
        padding: 1 2;
    }

    #refs-list {
        height: auto;
        max-height: 20;
        border: none;
    }
    """

    def __init__(
        self,
        symbol: str,
        results: list[tuple[str, int, int, str]],
        *,
        title: str = "References",
    ) -> None:
        """``results`` is a list of ``(path_str, line, column, snippet)`` tuples."""
        super().__init__()
        self._title = title
        self._symbol = symbol
        self._results = results

    def compose(self) -> ComposeResult:
        with Vertical(id="refs-panel"):
            yield Label(f"{self._title}: {self._symbol}", id="refs-title")
            if not self._results:
                yield Static("No references found.", id="refs-empty")
            else:
                options = [
                    Option(f"{Path(path).name}:{line}:{column}  {snippet[:60]}", id=str(i))
                    for i, (path, line, column, snippet) in enumerate(self._results)
                ]
                yield PointerTrackingOptionList(*options, id="refs-list")

    def on_mount(self) -> None:
        try:
            self.query_one("#refs-list", PointerTrackingOptionList).focus()
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = int(event.option_id)
        path_str, line, column, _snippet = self._results[idx]
        self.dismiss((path_str, line, column))


class GitCommitScreen(EscapeDismissMixin, ModalScreen[tuple[str, bool] | None]):
    """Full-featured commit screen: file list, diff preview, message input."""

    CSS = """
    GitCommitScreen {
        align: center middle;
    }

    #commit-dialog {
        width: 92%;
        height: 90%;
        border: solid #30363d;
        background: #161b22;
    }

    #commit-title-bar {
        height: 1;
        background: #21262d;
        color: #e6edf3;
        padding: 0 1;
        text-style: bold;
    }

    #commit-body {
        height: 1fr;
    }

    #file-panel {
        width: 32%;
        border-right: solid #21262d;
    }

    #file-panel-header {
        height: 1;
        background: #21262d;
        color: #8b949e;
        padding: 0 1;
    }

    #file-list {
        height: 1fr;
        background: #0d1117;
        border: none;
        padding: 0;
    }

    #file-list > ListItem {
        background: #0d1117;
        padding: 0 1;
    }

    #file-list > ListItem.--highlight {
        background: #1f2d3d;
    }

    #file-list > ListItem:hover {
        background: #2a2114;
    }

    #diff-panel {
        width: 1fr;
    }

    #diff-header {
        height: 1;
        background: #21262d;
        color: #8b949e;
        padding: 0 1;
    }

    #diff-container {
        height: 1fr;
        border: none;
        background: #0d1117;
    }

    #diff-container DiffView {
        height: 1fr;
    }

    #message-area {
        height: 4;
        border-top: solid #21262d;
        padding: 0 1;
    }

    #message-label {
        height: 1;
        color: #8b949e;
        padding-top: 0;
    }

    #message-input {
        height: 3;
        border: solid #30363d;
        background: #0d1117;
        color: #e6edf3;
    }

    #commit-actions {
        height: 3;
        align: right middle;
        padding: 0 1;
        border-top: solid #21262d;
    }

    #commit-actions Button {
        height: 1;
        min-height: 1;
        min-width: 10;
        padding: 0 2;
        border: none;
        margin-left: 1;
    }

    #discard-btn {
        background: #6e1a1a;
        color: #e5534b;
    }

    #discard-btn:hover {
        background: #a32020;
    }

    #do-commit-btn {
        background: #1a7f37;
        color: #ffffff;
    }

    #do-commit-btn:hover {
        background: #2ea043;
    }

    #do-commit-push-btn {
        background: #0969da;
        color: #ffffff;
    }

    #do-commit-push-btn:hover {
        background: #218bff;
    }

    .no-changes-label {
        color: #6e7681;
        padding: 1;
    }
    """

    _STATUS_COLORS: dict[str, str] = {
        "M": "#f7c96a",
        "A": "#57ab5a",
        "D": "#e5534b",
        "R": "#79c0ff",
        "C": "#79c0ff",
        "?": "#6e7681",
        "!": "#6e7681",
    }

    class FileDiscarded(Message):
        def __init__(self, path: Path) -> None:
            self.path = path
            super().__init__()

    def __init__(self, repo_root: Path, git_service) -> None:
        super().__init__()
        self.repo_root = repo_root
        self.git_service = git_service
        self._files: list[tuple[str, str]] = []  # (xy_status, filepath)
        self._current_diff_index: int | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="commit-dialog"):
            yield Label("Git Commit", id="commit-title-bar")
            with Horizontal(id="commit-body"):
                with Vertical(id="file-panel"):
                    yield Label("Changes", id="file-panel-header")
                    yield ListView(id="file-list")
                with Vertical(id="diff-panel"):
                    yield Label("Select a file to preview its diff", id="diff-header")
                    yield Vertical(id="diff-container")
            with Vertical(id="message-area"):
                yield Label("Commit message", id="message-label")
                yield Input(placeholder="Enter commit message…", id="message-input")
            with Horizontal(id="commit-actions"):
                yield Button("Cancel", id="cancel-btn", classes="dismiss-button")
                yield Button("Discard File", id="discard-btn", disabled=True)
                yield Button("Commit", id="do-commit-btn")
                yield Button("Commit & Push", id="do-commit-push-btn")

    def on_mount(self) -> None:
        branch = self.git_service.current_branch(self.repo_root) or "detached"
        self.query_one("#commit-title-bar", Label).update(
            f"Git Commit  —  {self.repo_root.name}  \u2387 {branch}"
        )
        self._refresh_file_list()
        try:
            self.query_one("#file-list", ListView).focus()
        except Exception:
            pass

    def _refresh_file_list(self) -> None:
        self._files = self.git_service.status_porcelain(self.repo_root)
        file_list = self.query_one("#file-list", ListView)
        header = self.query_one("#file-panel-header", Label)
        commit_button = self.query_one("#do-commit-btn", Button)
        commit_push_button = self.query_one("#do-commit-push-btn", Button)
        file_list.clear()
        header.update(f"Changes ({len(self._files)})")
        commit_button.disabled = not bool(self._files)
        commit_push_button.disabled = not bool(self._files)
        if not self._files:
            file_list.append(ListItem(Label("No changes to commit", classes="no-changes-label")))
            self._show_diff(None)
            return
        for xy, filepath in self._files:
            display = self._format_status_line(xy, filepath)
            file_list.append(ListItem(Static(display, markup=True)))
        file_list.index = 0
        self._show_diff(0)

    def _show_diff(self, index: int | None) -> None:
        self._current_diff_index = index
        discard_btn = self.query_one("#discard-btn", Button)
        discard_btn.disabled = index is None or index < 0 or index >= len(self._files)
        self.run_worker(self._load_diff(index), exclusive=True, group="diff-render")

    async def _load_diff(self, index: int | None) -> None:
        try:
            header = self.query_one("#diff-header", Label)
            container = self.query_one("#diff-container", Vertical)
        except Exception:
            return  # screen already dismissed

        await container.remove_children()

        if index is None or index < 0 or index >= len(self._files):
            header.update("Select a file to preview its diff")
            return

        _xy, filepath = self._files[index]
        header.update(f"  {filepath}")

        full_path = self.repo_root / filepath
        left_text = await asyncio.to_thread(
            lambda: self.git_service.show_file(self.repo_root, "HEAD", full_path) or ""
        )
        right_text = await asyncio.to_thread(
            lambda: full_path.read_text(encoding="utf-8", errors="replace") if full_path.exists() else ""
        )

        try:
            container = self.query_one("#diff-container", Vertical)
        except Exception:
            return  # dismissed while fetching

        await container.mount(DiffView("HEAD", left_text, filepath, right_text))

    def _format_status_line(self, xy: str, filepath: str) -> str:
        x, y = xy[0], xy[1] if len(xy) > 1 else " "
        # Show the most informative status letter
        letter = x if x.strip() else y
        color = self._STATUS_COLORS.get(letter.upper(), "#c9d1d9")
        filename = Path(filepath).name
        parent = str(Path(filepath).parent) if Path(filepath).parent != Path(".") else ""
        if parent:
            return f"[bold {color}]{xy}[/]  [dim]{parent}/[/][default]{filename}[/]"
        return f"[bold {color}]{xy}[/]  {filename}"

    @on(ListView.Highlighted, "#file-list")
    def _on_file_highlighted(self, event: ListView.Highlighted) -> None:
        self._show_diff(event.list_view.index)

    @on(ListView.Selected, "#file-list")
    def _on_file_selected(self, event: ListView.Selected) -> None:
        self._show_diff(event.list_view.index)

    @on(Button.Pressed, "#discard-btn")
    def _on_discard(self) -> None:
        idx = self._current_diff_index
        if idx is None or idx < 0 or idx >= len(self._files):
            return
        _xy, filepath = self._files[idx]
        ok, _output = self.git_service.restore_file(self.repo_root, filepath)
        if ok:
            self.notify(f"Discarded changes: {Path(filepath).name}")
            self.post_message(self.FileDiscarded(self.repo_root / filepath))
        else:
            self.notify(f"Failed to discard {Path(filepath).name}", severity="error")
        self._refresh_file_list()

    @on(Button.Pressed, "#cancel-btn")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#do-commit-btn")
    def _on_commit_button(self) -> None:
        self._submit_commit(push_after=False)

    @on(Button.Pressed, "#do-commit-push-btn")
    def _on_commit_push_button(self) -> None:
        self._submit_commit(push_after=True)

    @on(Input.Submitted, "#message-input")
    def _on_commit_enter(self, event: Input.Submitted) -> None:
        event.stop()
        self._submit_commit(push_after=False)

    def _submit_commit(self, *, push_after: bool) -> None:
        if not self._files:
            self.notify("No changes to commit", severity="warning")
            return
        message = self.query_one("#message-input", Input).value.strip()
        if not message:
            self.notify("Commit message cannot be empty", severity="warning")
            self.query_one("#message-input", Input).focus()
            return
        self.dismiss((message, push_after))


class _PushCommitItem(ListItem):
    """Selectable commit row for the push preview screen."""

    def __init__(self, entry: GitHistoryEntry) -> None:
        super().__init__()
        self.entry = entry

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold #79c0ff]{self.entry.commit}[/]  "
            f"[dim #8b949e]{self.entry.date}[/]  "
            f"[#e6edf3]{self.entry.subject}[/]",
            markup=True,
        )
        yield Static(f"[dim #6e7681]{self.entry.author}[/]", markup=True)


class _PushChangedFileItem(ListItem):
    """Selectable changed-file row inside push preview."""

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
        label = f"{self.old_file_path} → {self.file_path}" if self.old_file_path else self.file_path
        yield Static(f"[bold {color}]{self.file_status}[/]  [#e6edf3]{label}[/]", markup=True)


class GitPushScreen(ModalScreen[bool | None]):
    """Preview unpushed commits, changed files, and diffs before pushing."""

    BINDINGS = [
        Binding("escape", "escape_preview", "Back", show=False),
    ]

    CSS = """
    GitPushScreen {
        align: center middle;
    }

    #push-dialog {
        width: 96%;
        height: 90%;
        border: solid #30363d;
        background: #161b22;
    }

    #push-title-bar {
        height: 1;
        background: #21262d;
        color: #e6edf3;
        padding: 0 1;
        text-style: bold;
    }

    #push-body {
        height: 1fr;
    }

    #push-nav-panel {
        width: 30%;
        border-right: solid #21262d;
    }

    #push-diff-panel {
        width: 1fr;
    }

    .push-header {
        height: 1;
        background: #21262d;
        color: #8b949e;
        padding: 0 1;
    }

    #push-nav-header {
        height: 1;
        background: #21262d;
        color: #8b949e;
        padding: 0 1;
    }

    #push-nav-title {
        width: 1fr;
        height: 1;
        content-align: left middle;
    }

    #push-nav-back {
        width: auto;
        min-width: 0;
        height: 1;
        padding: 0 1;
        margin: 0;
    }

    #push-nav-list {
        height: 1fr;
        background: #0d1117;
        border: none;
        padding: 0;
    }

    #push-nav-list > ListItem {
        background: #0d1117;
        padding: 0 1;
    }

    #push-nav-list > ListItem.--highlight {
        background: #1f2d3d;
    }

    #push-nav-list > ListItem.hovered,
    #push-nav-list > ListItem:hover,
    #push-nav-list > ListItem.hovered.--highlight,
    #push-nav-list > ListItem:hover.--highlight {
        background: #8a5a16;
    }

    #push-nav-list Static {
        background: transparent;
    }

    #push-diff-container {
        height: 1fr;
        background: #0d1117;
        border: none;
    }

    #push-diff-container DiffView {
        height: 1fr;
    }

    #push-actions {
        height: 3;
        align: right middle;
        padding: 0 1;
        border-top: solid #21262d;
    }

    #push-actions Button {
        height: 1;
        min-height: 1;
        min-width: 10;
        padding: 0 2;
        border: none;
        margin-left: 1;
    }

    #do-push-btn {
        background: #0969da;
        color: #ffffff;
    }

    #do-push-btn:hover {
        background: #218bff;
    }

    .no-push-label {
        color: #6e7681;
        padding: 1;
    }
    """

    def __init__(self, repo_root: Path, git_service, entries: list[GitHistoryEntry]) -> None:
        super().__init__()
        self.repo_root = repo_root
        self.git_service = git_service
        self._entries = entries
        self._mode = "commits"
        self._current_commit_index: int | None = None
        self._current_file_index: int | None = None
        self._current_files: list[tuple[str, str, str | None]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="push-dialog"):
            yield Label("Push Preview", id="push-title-bar")
            with Horizontal(id="push-body"):
                with Vertical(id="push-nav-panel"):
                    with Horizontal(id="push-nav-header"):
                        yield Label("Commits to Push", id="push-nav-title")
                        yield Button("Back", id="push-nav-back", classes="dismiss-button")
                    yield ListView(id="push-nav-list")
                with Vertical(id="push-diff-panel"):
                    yield Label("Select a file to preview its diff", classes="push-header", id="push-diff-header")
                    yield Vertical(id="push-diff-container")
            with Horizontal(id="push-actions"):
                yield Button("Cancel", id="push-cancel-btn", classes="dismiss-button")
                yield Button("Push", id="do-push-btn", disabled=not bool(self._entries))

    def on_mount(self) -> None:
        branch = self.git_service.current_branch(self.repo_root) or "detached"
        self.query_one("#push-title-bar", Label).update(
            f"Push Preview  —  {self.repo_root.name}  ⎇ {branch}"
        )
        self._show_commits()
        try:
            self.query_one("#push-nav-list", ListView).focus()
        except Exception:
            pass

    def action_escape_preview(self) -> None:
        """Handle the screen-local Escape binding."""
        self.handle_escape()

    def handle_escape(self) -> bool:
        """Handle Escape locally and return whether it was consumed."""
        if self._mode == "files":
            self._show_commits()
            try:
                self.query_one("#push-nav-list", ListView).focus()
            except Exception:
                pass
            return True
        self.dismiss(None)
        return True

    def _show_commits(self) -> None:
        self._mode = "commits"
        self._current_commit_index = None
        self._current_file_index = None
        self._current_files = []
        nav_title = self.query_one("#push-nav-title", Label)
        nav_list = self.query_one("#push-nav-list", ListView)
        back = self.query_one("#push-nav-back", Button)
        nav_title.update("Commits to Push")
        back.display = False
        nav_list.clear()
        if not self._entries:
            nav_list.append(ListItem(Label("No unpushed commits", classes="no-push-label")))
            self._show_diff(None)
            return
        for entry in self._entries:
            nav_list.append(_PushCommitItem(entry))
        nav_list.index = 0
        self.query_one("#push-diff-header", Label).update("Select a commit, then a file to preview its diff")
        self._show_diff(None)

    def _show_files_for_commit(self, index: int | None) -> None:
        self._mode = "files"
        self._current_commit_index = index
        nav_list = self.query_one("#push-nav-list", ListView)
        nav_title = self.query_one("#push-nav-title", Label)
        back = self.query_one("#push-nav-back", Button)
        nav_list.clear()
        self._current_files = []
        self._current_file_index = None

        if index is None or index < 0 or index >= len(self._entries):
            nav_title.update("Changed Files")
            back.display = True
            self._show_diff(None)
            return

        entry = self._entries[index]
        self._current_files = self.git_service.files_changed_in_commit(self.repo_root, entry.commit)
        nav_title.update(f"Files in {entry.commit[:8]}")
        back.display = True
        if not self._current_files:
            nav_list.append(ListItem(Label("No file changes recorded", classes="no-push-label")))
            self._show_diff(None)
            return

        for status, filepath, old_filepath in self._current_files:
            nav_list.append(_PushChangedFileItem(status, filepath, old_filepath))
        nav_list.index = 0
        self._show_diff(0)

    def _show_diff(self, index: int | None) -> None:
        self._current_file_index = index
        self.run_worker(self._load_diff(index), exclusive=True, group="push-diff-render")

    async def _load_diff(self, index: int | None) -> None:
        try:
            header = self.query_one("#push-diff-header", Label)
            container = self.query_one("#push-diff-container", Vertical)
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
                lambda: self.git_service.show_file(self.repo_root, f"{commit}~1", self.repo_root / source)
            )
            before_text = before_raw if before_raw is not None else ""
            before_label = f"{short}~1:{source}"

        if status == "D":
            after_text = ""
            after_label = "/dev/null"
        else:
            after_raw = await asyncio.to_thread(
                lambda: self.git_service.show_file(self.repo_root, commit, self.repo_root / filepath)
            )
            after_text = after_raw if after_raw is not None else ""
            after_label = f"{short}:{filepath}"

        await container.mount(DiffView(before_label, before_text, after_label, after_text))

    @on(ListView.Highlighted, "#push-nav-list")
    def _on_nav_highlighted(self, event: ListView.Highlighted) -> None:
        if self._mode == "files":
            self._show_diff(event.list_view.index)

    @on(ListView.Selected, "#push-nav-list")
    def _on_nav_selected(self, event: ListView.Selected) -> None:
        if self._mode == "commits":
            self._show_files_for_commit(event.list_view.index)
            return
        self._show_diff(event.list_view.index)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Keep the whole hovered row highlighted, including two-line commit items."""
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
        for item in self.query("#push-nav-list > ListItem"):
            if item is target:
                item.add_class("hovered")
            else:
                item.remove_class("hovered")

    def on_leave(self) -> None:
        for item in self.query("#push-nav-list > ListItem"):
            item.remove_class("hovered")

    @on(Button.Pressed, "#push-nav-back")
    def _on_back_to_commits(self) -> None:
        self._show_commits()

    @on(Button.Pressed, "#push-cancel-btn")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#do-push-btn")
    def _on_push(self) -> None:
        self.dismiss(True)
