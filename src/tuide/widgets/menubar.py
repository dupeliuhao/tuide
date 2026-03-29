"""Simple top command bar for tuide."""

from __future__ import annotations

from textual.containers import Horizontal
from textual.widgets import Button


class MenuBar(Horizontal):
    """A lightweight top menu bar composed of action buttons."""

    DEFAULT_CLASSES = "menu-bar"

    def compose(self):
        yield Button("Add Root", id="menu-add-root")
        yield Button("Remove Root", id="menu-remove-root")
        yield Button("Quick Open", id="menu-quick-open")
        yield Button("Find", id="menu-find-file")
        yield Button("Find WS", id="menu-find-workspace")
        yield Button("Palette", id="menu-palette")
        yield Button("Diff", id="menu-git-diff")
        yield Button("History", id="menu-git-history")
        yield Button("Blame", id="menu-git-blame")
        yield Button("Line Hist", id="menu-git-line-history")
        yield Button("Go To Def", id="menu-code-def")
        yield Button("Refs", id="menu-code-refs")
