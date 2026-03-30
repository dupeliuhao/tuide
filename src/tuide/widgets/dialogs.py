"""Modal dialogs for tuide."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList
from textual.widgets.option_list import Option

from tuide.models import ChoiceItem, CommandItem


class ConfirmDialog(ModalScreen[bool | None]):
    """A simple confirm / cancel dialog."""

    CSS = """
    ConfirmDialog {
        align: center middle;
    }

    #confirm-dialog {
        width: 60;
        height: auto;
        border: round #d7a84a;
        background: #17212b;
        padding: 1 2;
    }

    #confirm-title {
        text-style: bold;
        color: #f3efe2;
        padding-bottom: 1;
    }

    #confirm-message {
        color: #d9e2ec;
        padding-bottom: 1;
    }

    #confirm-hint {
        color: #8fa3b8;
        padding-bottom: 1;
    }

    #confirm-actions {
        width: 100%;
        height: auto;
        align: right middle;
    }

    #confirm-actions Button {
        margin-left: 1;
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


class HelpDialog(ModalScreen[None]):
    """A lightweight keybinding help overlay."""

    CSS = """
    HelpDialog {
        align: center middle;
    }

    #help-dialog {
        width: 72;
        height: auto;
        max-height: 90%;
        border: round #d7a84a;
        background: #17212b;
        padding: 1 2;
    }

    #help-title {
        text-style: bold;
        color: #f3efe2;
        padding-bottom: 1;
    }

    .help-line {
        color: #d9e2ec;
    }

    #help-close {
        margin-top: 1;
        width: 16;
        align-horizontal: right;
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


class PromptDialog(ModalScreen[str | None]):
    """Prompt for a single text value."""

    CSS = """
    PromptDialog {
        align: center middle;
    }

    #prompt-dialog {
        width: 72;
        height: auto;
        border: round #d7a84a;
        background: #17212b;
        padding: 1 2;
    }

    #prompt-title {
        text-style: bold;
        color: #f3efe2;
        padding-bottom: 1;
    }

    #prompt-input {
        margin-bottom: 1;
    }

    #prompt-hint {
        color: #8fa3b8;
        padding-bottom: 1;
    }

    #prompt-actions {
        width: 100%;
        height: auto;
        align: right middle;
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


class CommandPaletteDialog(ModalScreen[str | None]):
    """Searchable command palette."""

    CSS = """
    CommandPaletteDialog {
        align: center middle;
    }

    #palette-dialog {
        width: 80;
        height: 24;
        border: round #d7a84a;
        background: #17212b;
        padding: 1 2;
    }

    #palette-title {
        text-style: bold;
        color: #f3efe2;
        padding-bottom: 1;
    }

    #palette-input {
        margin-bottom: 1;
    }

    #palette-options {
        height: 1fr;
    }

    #palette-actions {
        width: 100%;
        height: auto;
        align: right middle;
        margin-top: 1;
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


class OptionPickerDialog(ModalScreen[str | None]):
    """Pick from a list of options with lightweight filtering."""

    CSS = """
    OptionPickerDialog {
        align: center middle;
    }

    #picker-dialog {
        width: 84;
        height: 26;
        border: round #d7a84a;
        background: #17212b;
        padding: 1 2;
    }

    #picker-title {
        text-style: bold;
        color: #f3efe2;
        padding-bottom: 1;
    }

    #picker-input {
        margin-bottom: 1;
    }

    #picker-options {
        height: 1fr;
    }

    #picker-actions {
        width: 100%;
        height: auto;
        align: right middle;
        margin-top: 1;
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
