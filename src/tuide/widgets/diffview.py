"""Read-only side-by-side diff widgets."""

from __future__ import annotations

import difflib

from rich.text import Text
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label, Static

_EQUAL_STYLE = "#c9d1d9"
_REMOVED_STYLE = "#ff8888 on #2d1010"
_ADDED_STYLE = "#89d185 on #0d2a0d"
_GUTTER_STYLE = "dim #6e7681"


def _build_diff_markup(left_lines: list[str], right_lines: list[str]) -> tuple[Text, Text]:
    """Return (left_rich, right_rich) with per-line diff highlighting."""
    left_rich = Text(no_wrap=True, overflow="fold")
    right_rich = Text(no_wrap=True, overflow="fold")

    matcher = difflib.SequenceMatcher(None, left_lines, right_lines, autojunk=False)
    left_ln = 1
    right_ln = 1

    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == "equal":
            for line in left_lines[a0:a1]:
                left_rich.append(f"{left_ln:4} \u2502 ", style=_GUTTER_STYLE)
                left_rich.append(f"{line}\n", style=_EQUAL_STYLE)
                left_ln += 1
            for line in right_lines[b0:b1]:
                right_rich.append(f"{right_ln:4} \u2502 ", style=_GUTTER_STYLE)
                right_rich.append(f"{line}\n", style=_EQUAL_STYLE)
                right_ln += 1
        elif opcode == "replace":
            for line in left_lines[a0:a1]:
                left_rich.append(f"{left_ln:4} \u2502 ", style=_GUTTER_STYLE)
                left_rich.append(f"- {line}\n", style=_REMOVED_STYLE)
                left_ln += 1
            for line in right_lines[b0:b1]:
                right_rich.append(f"{right_ln:4} \u2502 ", style=_GUTTER_STYLE)
                right_rich.append(f"+ {line}\n", style=_ADDED_STYLE)
                right_ln += 1
        elif opcode == "delete":
            for line in left_lines[a0:a1]:
                left_rich.append(f"{left_ln:4} \u2502 ", style=_GUTTER_STYLE)
                left_rich.append(f"- {line}\n", style=_REMOVED_STYLE)
                left_ln += 1
        elif opcode == "insert":
            for line in right_lines[b0:b1]:
                right_rich.append(f"{right_ln:4} \u2502 ", style=_GUTTER_STYLE)
                right_rich.append(f"+ {line}\n", style=_ADDED_STYLE)
                right_ln += 1

    return left_rich, right_rich


class DiffView(Horizontal):
    """Two-pane read-only diff display with line-level highlighting."""

    DEFAULT_CLASSES = "diff-view"

    def __init__(self, left_title: str, left_text: str, right_title: str, right_text: str) -> None:
        super().__init__()
        self.left_title = left_title
        self.left_text = left_text
        self.right_title = right_title
        self.right_text = right_text

    def compose(self):
        left_lines = self.left_text.splitlines()
        right_lines = self.right_text.splitlines()
        left_rich, right_rich = _build_diff_markup(left_lines, right_lines)

        with Vertical(classes="diff-pane"):
            yield Label(self.left_title, classes="panel-subtitle")
            with VerticalScroll():
                yield Static(left_rich, id="diff-left", classes="diff-content")
        with Vertical(classes="diff-pane"):
            yield Label(self.right_title, classes="panel-subtitle")
            with VerticalScroll():
                yield Static(right_rich, id="diff-right", classes="diff-content")
