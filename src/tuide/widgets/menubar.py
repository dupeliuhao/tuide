"""Compact top command bar for tuide."""

from __future__ import annotations

from textual.containers import Horizontal
from textual.widgets import Button


class MenuBar(Horizontal):
    """A compact top action bar."""

    DEFAULT_CLASSES = "menu-bar"

    def compose(self):
        yield Button("+Root", id="menu-add-root", classes="menu-button")
        yield Button("-Root", id="menu-remove-root", classes="menu-button")
        yield Button("Open", id="menu-quick-open", classes="menu-button")
        yield Button("Find", id="menu-find-file", classes="menu-button")
        yield Button("Find WS", id="menu-find-workspace", classes="menu-button")
        yield Button("Cmd", id="menu-palette", classes="menu-button")
        yield Button("Diff", id="menu-git-diff", classes="menu-button")
        yield Button("Hist", id="menu-git-history", classes="menu-button")
        yield Button("Blame", id="menu-git-blame", classes="menu-button")
        yield Button("Line", id="menu-git-line-history", classes="menu-button")
        yield Button("Def", id="menu-code-def", classes="menu-button")
        yield Button("Refs", id="menu-code-refs", classes="menu-button")
        yield Button("Quit", id="menu-quit", classes="menu-button")
