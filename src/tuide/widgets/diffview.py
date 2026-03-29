"""Read-only side-by-side diff widgets."""

from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.widgets import Label, TextArea


class DiffView(Horizontal):
    """Two-pane read-only diff display."""

    DEFAULT_CLASSES = "diff-view"

    def __init__(self, left_title: str, left_text: str, right_title: str, right_text: str) -> None:
        super().__init__()
        self.left_title = left_title
        self.left_text = left_text
        self.right_title = right_title
        self.right_text = right_text

    def compose(self):
        with Vertical(classes="diff-pane"):
            yield Label(self.left_title, classes="panel-subtitle")
            left = TextArea(text=self.left_text, read_only=True, id="diff-left")
            left.show_line_numbers = True
            yield left
        with Vertical(classes="diff-pane"):
            yield Label(self.right_title, classes="panel-subtitle")
            right = TextArea(text=self.right_text, read_only=True, id="diff-right")
            right.show_line_numbers = True
            yield right
