"""Structured top command bar for tuide."""

from __future__ import annotations

from textual.containers import Horizontal
from textual.widgets import Button, Static


class MenuBar(Horizontal):
    """A lightweight top menu bar grouped by intent."""

    DEFAULT_CLASSES = "menu-bar"

    def compose(self):
        yield Static("Workspace", classes="menu-group-label")
        yield Button("Add Root", id="menu-add-root", classes="menu-button")
        yield Button("Remove", id="menu-remove-root", classes="menu-button")
        yield Button("Quick Open", id="menu-quick-open", classes="menu-button")
        yield Static("Search", classes="menu-group-label")
        yield Button("Find File", id="menu-find-file", classes="menu-button")
        yield Button("Find WS", id="menu-find-workspace", classes="menu-button")
        yield Button("Palette", id="menu-palette", classes="menu-button")
        yield Static("Git", classes="menu-group-label")
        yield Button("Diff", id="menu-git-diff", classes="menu-button")
        yield Button("History", id="menu-git-history", classes="menu-button")
        yield Button("Blame", id="menu-git-blame", classes="menu-button")
        yield Static("Code", classes="menu-group-label")
        yield Button("Line Hist", id="menu-git-line-history", classes="menu-button")
        yield Button("Go To Def", id="menu-code-def", classes="menu-button")
        yield Button("Refs", id="menu-code-refs", classes="menu-button")
