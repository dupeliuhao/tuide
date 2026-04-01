"""Modal dialogs for tuide."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.geometry import Spacing
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from tuide.models import ChoiceItem, CommandItem


class EscapeDismissMixin:
    """Mixin that makes Escape dismiss the active modal."""

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(None)
            event.stop()


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
    ) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(self._title, id="confirm-title")
            yield Label(self._message, id="confirm-message")
            yield Label("Esc or Back to return", id="confirm-hint")
            with Horizontal(id="confirm-actions"):
                yield Button("Back", id="confirm-cancel")
                yield Button(self._confirm_label, variant="warning", id="confirm-ok")

    def on_mount(self) -> None:
        """Focus the safest action first."""
        self.query_one("#confirm-cancel", Button).focus()

    def action_cancel(self) -> None:
        """Dismiss without confirming."""
        self.dismiss(None)

    def action_confirm(self) -> None:
        """Dismiss with confirmation."""
        self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
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
        with Vertical(id="help-dialog"):
            yield Label("tuide keybindings", id="help-title")
            yield Label("Tab / Shift+Tab  cycle focus between panels", classes="help-line")
            yield Label("Esc              return focus to the editor", classes="help-line")
            yield Label("Ctrl+S           save active file", classes="help-line")
            yield Label("Ctrl+W           close active tab", classes="help-line")
            yield Label("Ctrl+Q           quit with unsaved-changes prompt", classes="help-line")
            yield Label("Ctrl+B           toggle workspace panel", classes="help-line")
            yield Label("Ctrl+J           toggle terminal panel", classes="help-line")
            yield Label("Ctrl+R           restart terminal", classes="help-line")
            yield Label("?                show this help", classes="help-line")
            yield Button("Close", id="help-close")

    def on_mount(self) -> None:
        """Focus the close button."""
        self.query_one("#help-close", Button).focus()

    def action_close_help(self) -> None:
        """Dismiss the help overlay."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss on button press."""
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
                yield Button("Back", id="prompt-cancel")
                yield Button("OK", variant="success", id="prompt-ok")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss(self.query_one("#prompt-input", Input).value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
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
            yield OptionList(*options, id="palette-options")
            with Horizontal(id="palette-actions"):
                yield Button("Back", id="palette-cancel")

    def on_mount(self) -> None:
        self.query_one("#palette-input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
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
        option_list = self.query_one("#palette-options", OptionList)
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
        width: 76;
        height: auto;
        max-height: 85%;
        border: solid #30363d;
        background: #161b22;
        padding: 0 1;
    }

    #picker-title {
        text-style: bold;
        color: #e6edf3;
        padding-bottom: 0;
    }

    #picker-input {
        margin-bottom: 0;
    }

    #picker-options {
        height: 10;
        min-height: 6;
    }

    #picker-actions {
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

    def __init__(self, title: str, options: list[ChoiceItem], placeholder: str = "Type to filter") -> None:
        super().__init__()
        self._title = title
        self._options = options
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-dialog"):
            yield Label(self._title, id="picker-title")
            yield Input(placeholder=self._placeholder, id="picker-input")
            options = [Option(self._format_option(item), id=item.id) for item in self._options]
            yield OptionList(*options, id="picker-options")
            with Horizontal(id="picker-actions"):
                yield Button("Back", id="picker-cancel")

    def on_mount(self) -> None:
        self.query_one("#picker-input", Input).focus()
        option_list = self.query_one("#picker-options", OptionList)
        if option_list.option_count:
            option_list.highlighted = 0

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "picker-cancel":
            self.dismiss(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "picker-input":
            return
        query = event.value.strip().lower()
        option_list = self.query_one("#picker-options", OptionList)
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

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option_id)

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
        width: 38;
        height: auto;
        max-height: 20;
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

    #branch-list {
        height: auto;
        max-height: 18;
        border: none;
    }
    """

    def __init__(self, branches: list[str], current: str) -> None:
        super().__init__()
        self._branches = branches
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="branch-picker"):
            yield Label("switch branch", id="branch-picker-title")
            options = [
                Option(("* " if b == self._current else "  ") + b, id=b)
                for b in self._branches
            ]
            yield OptionList(*options, id="branch-list")

    def on_mount(self) -> None:
        ol = self.query_one("#branch-list", OptionList)
        try:
            ol.highlighted = self._branches.index(self._current)
        except ValueError:
            pass
        ol.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option_id)


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
            yield OptionList(
                *[Option(item.label, id=item.id) for item in self._items],
                id="context-menu-list",
            )

    def on_mount(self) -> None:
        self.call_after_refresh(self._position_menu)
        self.query_one("#context-menu-list", OptionList).focus()

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


class FindReferencesScreen(EscapeDismissMixin, ModalScreen[tuple[str, int] | None]):
    """Bottom-right popup showing find-references results.

    Returns ``(path_str, line_number)`` when the user selects an entry, or
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

    def __init__(self, symbol: str, results: list[tuple[str, int, str]]) -> None:
        """``results`` is a list of ``(path_str, line, snippet)`` tuples."""
        super().__init__()
        self._symbol = symbol
        self._results = results

    def compose(self) -> ComposeResult:
        with Vertical(id="refs-panel"):
            yield Label(f"References: {self._symbol}", id="refs-title")
            if not self._results:
                yield Static("No references found.", id="refs-empty")
            else:
                options = [
                    Option(f"{Path(path).name}:{line}  {snippet[:60]}", id=str(i))
                    for i, (path, line, snippet) in enumerate(self._results)
                ]
                yield OptionList(*options, id="refs-list")

    def on_mount(self) -> None:
        try:
            self.query_one("#refs-list", OptionList).focus()
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = int(event.option_id)
        path_str, line, _snippet = self._results[idx]
        self.dismiss((path_str, line))
