"""Read-only diff display, using delta when available."""

from __future__ import annotations

import difflib
import shutil
import subprocess

from rich.text import Text
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label, Static

_EQUAL_STYLE = "#c9d1d9"
_REMOVED_STYLE = "#ff8888 on #2d1010"
_ADDED_STYLE = "#89d185 on #0d2a0d"
_GUTTER_STYLE = "dim #6e7681"


# ---------------------------------------------------------------------------
# delta path
# ---------------------------------------------------------------------------

def _delta_available() -> bool:
    return shutil.which("delta") is not None


def _run_delta(
    left_title: str,
    left_text: str,
    right_title: str,
    right_text: str,
    width: int,
    *,
    full_context: bool = False,
) -> str | None:
    """Pipe a unified diff through delta and return the ANSI output, or None on failure."""
    left_lines = left_text.splitlines(keepends=True)
    right_lines = right_text.splitlines(keepends=True)
    context_lines = max(len(left_lines), len(right_lines)) if full_context else 3

    unified = difflib.unified_diff(
        left_lines, right_lines,
        fromfile=left_title,
        tofile=right_title,
        n=context_lines,
    )
    diff_input = "".join(unified)

    try:
        result = subprocess.run(
            [
                "delta",
                f"--width={width}",
                "--side-by-side",
                "--line-numbers",
                "--syntax-theme=GitHub",
                "--hunk-header-style=file line-number syntax",
                "--hunk-header-decoration-style=box",
            ],
            input=diff_input,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout
    except Exception:
        return None


def _pad_cell(text: str, width: int) -> str:
    visible = text.expandtabs(4)
    if len(visible) > width:
        return visible[: max(0, width - 1)] + "…"
    return visible.ljust(width)


# ---------------------------------------------------------------------------
# Fallback: plain two-pane markup (no delta)
# ---------------------------------------------------------------------------

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


def _build_side_by_side_markup(left_lines: list[str], right_lines: list[str], width: int) -> Text:
    """Return a single shared-scroll side-by-side diff rendering."""
    content = Text(no_wrap=True, overflow="ignore")
    left_width = max(24, (width - 18) // 2)
    right_width = max(24, width - left_width - 18)
    matcher = difflib.SequenceMatcher(None, left_lines, right_lines, autojunk=False)
    left_ln = 1
    right_ln = 1

    def append_row(
        left_number: int | None,
        left_text: str,
        left_style: str,
        right_number: int | None,
        right_text: str,
        right_style: str,
    ) -> None:
        if left_number is None:
            content.append("     ", style=_GUTTER_STYLE)
        else:
            content.append(f"{left_number:4} ", style=_GUTTER_STYLE)
        content.append("│ ", style=_GUTTER_STYLE)
        content.append(_pad_cell(left_text, left_width), style=left_style)
        content.append(" │ ", style=_GUTTER_STYLE)
        if right_number is None:
            content.append("     ", style=_GUTTER_STYLE)
        else:
            content.append(f"{right_number:4} ", style=_GUTTER_STYLE)
        content.append("│ ", style=_GUTTER_STYLE)
        content.append(_pad_cell(right_text, right_width), style=right_style)
        content.append("\n")

    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        left_chunk = left_lines[a0:a1]
        right_chunk = right_lines[b0:b1]
        row_count = max(len(left_chunk), len(right_chunk))
        for row_index in range(row_count):
            left_line = left_chunk[row_index] if row_index < len(left_chunk) else None
            right_line = right_chunk[row_index] if row_index < len(right_chunk) else None

            if opcode == "equal":
                left_style = right_style = _EQUAL_STYLE
            elif opcode == "insert":
                left_style = _EQUAL_STYLE
                right_style = _ADDED_STYLE
            elif opcode == "delete":
                left_style = _REMOVED_STYLE
                right_style = _EQUAL_STYLE
            else:
                left_style = _REMOVED_STYLE
                right_style = _ADDED_STYLE

            append_row(
                left_ln if left_line is not None else None,
                left_line or "",
                left_style,
                right_ln if right_line is not None else None,
                right_line or "",
                right_style,
            )

            if left_line is not None:
                left_ln += 1
            if right_line is not None:
                right_ln += 1

    return content


def render_side_by_side_diff(
    left_title: str,
    left_text: str,
    right_title: str,
    right_text: str,
    width: int,
    *,
    full_context: bool = False,
) -> Text:
    """Render a side-by-side diff into a single rich Text block."""
    if _delta_available():
        output = _run_delta(
            left_title,
            left_text,
            right_title,
            right_text,
            width,
            full_context=full_context,
        )
        if output:
            return Text.from_ansi(output)

    return _build_side_by_side_markup(
        left_text.splitlines(),
        right_text.splitlines(),
        width,
    )


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class DiffView(Horizontal):
    """Diff display: single-pane delta output when delta is installed, two-pane fallback otherwise."""

    DEFAULT_CLASSES = "diff-view"

    def __init__(self, left_title: str, left_text: str, right_title: str, right_text: str) -> None:
        super().__init__()
        self.left_title = left_title
        self.left_text = left_text
        self.right_title = right_title
        self.right_text = right_text

    def compose(self):
        if _delta_available():
            with VerticalScroll():
                yield Static("", id="delta-content", classes="diff-content")
        else:
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

    def on_mount(self) -> None:
        if _delta_available():
            self.call_after_refresh(self._render_delta)

    def _render_delta(self) -> None:
        width = self.size.width or shutil.get_terminal_size().columns
        content = self.query_one("#delta-content", Static)
        content.update(
            render_side_by_side_diff(
                self.left_title,
                self.left_text,
                self.right_title,
                self.right_text,
                width,
            )
        )
