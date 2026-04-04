"""Terminal host widget with optional textual-terminal integration."""

from __future__ import annotations

import os
import pty
import shlex
from pathlib import Path

from textual import events, on
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Static, Tab, TabPane, TabbedContent


def _patch_terminal_env() -> None:
    """Patch textual_terminal to inherit the user's full shell environment.

    The library's TerminalEmulator.open_terminal uses a hardcoded minimal env
    (only TERM, LC_ALL, HOME). This patch replaces that with os.environ so the
    embedded shell sees the user's PATH, aliases, and other variables.
    """
    try:
        from textual_terminal._terminal import TerminalEmulator

        def _open_terminal(self, command: str) -> int:
            self.pid, fd = pty.fork()
            if self.pid == 0:
                argv = shlex.split(command)
                env = os.environ.copy()
                env["TERM"] = "xterm"
                env.setdefault("LC_ALL", "en_US.UTF-8")
                env["HOME"] = str(Path.home())
                os.execvpe(argv[0], argv, env)
            return fd

        TerminalEmulator.open_terminal = _open_terminal
    except Exception:
        pass


def terminal_backend_available() -> bool:
    """Return whether textual-terminal can be imported."""
    try:
        from textual_terminal import Terminal  # noqa: F401
    except Exception:
        return False
    return True


class TerminalPanel(Vertical):
    """Linux-first terminal panel with multi-tab support."""

    DEFAULT_CLASSES = "panel-frame"
    can_focus = True

    class HideRequested(Message):
        """Request that the owning app hide the terminal panel."""

    def __init__(self, shell_hint: str) -> None:
        super().__init__(id="terminal-panel")
        self.shell_hint = shell_hint
        self._tab_counter = 0
        # Maps pane_id -> real Terminal widget (only real backends, not fallbacks)
        self._terminal_widgets: dict[str, object] = {}

    def _next_tab_num(self) -> int:
        self._tab_counter += 1
        return self._tab_counter

    def _build_terminal_widget(self, widget_id: str) -> tuple[object, bool]:
        """Build a terminal widget. Returns (widget, is_real_terminal)."""
        try:
            _patch_terminal_env()
            from textual_terminal import Terminal

            return Terminal(command=self.shell_hint, id=widget_id), True
        except Exception:
            return (
                Static(
                    f"Terminal unavailable\n\ntextual-terminal could not be loaded."
                    f"\nShell: {self.shell_hint}\n\nInstall with: pip install textual-terminal",
                    classes="terminal-fallback-copy",
                    id=widget_id,
                ),
                False,
            )

    def compose(self):
        n = self._next_tab_num()
        pane_id = f"term-tab-{n}"
        widget, is_real = self._build_terminal_widget(f"embedded-terminal-{n}")
        if is_real:
            self._terminal_widgets[pane_id] = widget
        yield Button("+", id="new-terminal-tab-btn", classes="terminal-add-btn")
        with TabbedContent(id="terminal-tabs"):
            with TabPane(self._tab_label(n), id=pane_id):
                yield widget

    def on_mount(self) -> None:
        """Start all terminal sessions after mounting."""
        for widget in self._terminal_widgets.values():
            try:
                widget.start()
            except Exception:
                pass

    @property
    def _tabs(self) -> TabbedContent:
        return self.query_one("#terminal-tabs", TabbedContent)

    @staticmethod
    def _tab_label(n: int) -> str:
        return f"Terminal {n}  ×"

    async def new_tab(self) -> None:
        """Open a new terminal tab and focus it."""
        n = self._next_tab_num()
        pane_id = f"term-tab-{n}"
        widget, is_real = self._build_terminal_widget(f"embedded-terminal-{n}")
        pane = TabPane(self._tab_label(n), widget, id=pane_id)
        tabs = self._tabs
        await tabs.add_pane(pane)
        tabs.active = pane_id
        tabs.refresh(layout=True)
        self.refresh(layout=True)
        if is_real:
            self._terminal_widgets[pane_id] = widget

            def _start_and_focus() -> None:
                self.refresh(layout=True)
                tabs.refresh(layout=True)
                widget.start()
                widget.focus()

            self.call_after_refresh(_start_and_focus)

    def _renumber_tabs(self) -> None:
        """Relabel remaining terminal tabs with sequential 1-based indices."""
        tabs = self._tabs
        for i, pane in enumerate(tabs.query("TabPane"), start=1):
            label = self._tab_label(i)
            pane.title = label
            try:
                tabs.get_tab(pane.id).label = label
            except Exception:
                pass

    async def close_active_tab(self) -> bool:
        """Close the active terminal tab. Returns False if it's the last one."""
        tabs = self._tabs
        if tabs.tab_count <= 1:
            self.post_message(self.HideRequested())
            return False
        active_id = tabs.active
        widget = self._terminal_widgets.pop(active_id, None)
        if widget is not None:
            try:
                widget.terminate()
            except Exception:
                pass
        await tabs.remove_pane(active_id)
        self._renumber_tabs()
        return True

    def restart_active(self) -> bool:
        """Restart the active terminal session."""
        active_id = self._tabs.active
        widget = self._terminal_widgets.get(active_id)
        if widget is None:
            return False
        try:
            widget.terminate()
        except Exception:
            pass
        widget.start()
        return True

    def restart(self) -> bool:
        """Restart the active terminal (backward-compat alias)."""
        return self.restart_active()

    @on(events.Click)
    def _on_tab_close_click(self, event: events.Click) -> None:
        """Close a terminal tab when the × at the end of its label is clicked."""
        tab = event._sender
        if not isinstance(tab, Tab):
            return
        if event.x < tab.size.width - 3:
            return
        event.stop()
        pane_id = tab.id.removeprefix("tab-")
        self.run_worker(self._close_terminal_pane(pane_id), exclusive=False)

    async def _close_terminal_pane(self, pane_id: str) -> None:
        """Terminate and remove a specific terminal pane."""
        tabs = self._tabs
        if tabs.tab_count <= 1:
            self.post_message(self.HideRequested())
            return
        widget = self._terminal_widgets.pop(pane_id, None)
        if widget is not None:
            try:
                widget.terminate()
            except Exception:
                pass
        try:
            await tabs.remove_pane(pane_id)
        except Exception:
            pass
        self._renumber_tabs()
