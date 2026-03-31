"""Compact top command bar for tuide."""

from __future__ import annotations

from textual.containers import Horizontal
from textual.widgets import Button


class MenuBar(Horizontal):
    """A compact top action bar."""

    DEFAULT_CLASSES = "menu-bar"

    def compose(self):
        yield Button("+", id="menu-add-root", classes="menu-button")
        yield Button("-", id="menu-remove-root", classes="menu-button")
        yield Button("Git", id="menu-git-session", classes="menu-button")
