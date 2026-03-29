"""Terminal host widget with optional textual-terminal integration."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Label, Static


def terminal_backend_available() -> bool:
    """Return whether textual-terminal can be imported."""
    try:
        from textual_terminal import Terminal  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


class TerminalPanel(Vertical):
    """Linux-first terminal panel with graceful fallback behavior."""

    DEFAULT_CLASSES = "panel-frame"
    can_focus = True

    def __init__(self, shell_hint: str) -> None:
        super().__init__(id="terminal-panel")
        self.shell_hint = shell_hint
        self._terminal_widget = None
        self._fallback: Static | None = None

    def compose(self):
        yield Label("Terminal", classes="panel-title")
        yield Label(f"Shell: {self.shell_hint}", classes="panel-subtitle", id="terminal-subtitle")
        fallback = self._build_terminal_widget()
        if fallback is not None:
            self._fallback = fallback
            yield fallback

    def _build_terminal_widget(self):
        """Try to build a real terminal widget, otherwise return a fallback view."""
        try:
            from textual_terminal import Terminal
        except ModuleNotFoundError:
            self._terminal_widget = None
            return Static(
                "Install `textual-terminal` to enable the embedded Linux terminal.\n\n"
                "Current shell target:\n"
                f"{self.shell_hint}",
                classes="panel-body",
                id="terminal-fallback",
            )

        terminal = Terminal(command=self.shell_hint, id="embedded-terminal")
        self._terminal_widget = terminal
        return terminal

    def on_mount(self) -> None:
        """Start the terminal session when available."""
        if self._terminal_widget is not None:
            self._terminal_widget.start()

    def restart(self) -> bool:
        """Restart the terminal session when available."""
        if self._terminal_widget is None:
            return False

        try:
            self._terminal_widget.terminate()
        except Exception:
            pass
        self._terminal_widget.start()
        return True
