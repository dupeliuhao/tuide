"""Editor widgets for the Linux-first shell."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.geometry import Size
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Static, TextArea
from textual.widgets.text_area import TextAreaTheme

from tuide.models import OpenDocument
from tuide.widgets.diffview import DiffView


# ---------------------------------------------------------------------------
# Helpers shared by WrappingTabBar and EditorPanel
# ---------------------------------------------------------------------------

_CLOSE = "  ×"   # 3 cells: two spaces + ×
_SEP   = "▏"     # 1-cell separator between tabs
_PAD   = 1        # cells of padding on each side inside a tab label
_MAX_NAME = 18    # max filename chars before truncation


def _truncate(name: str) -> str:
    if len(name) > _MAX_NAME:
        return name[: _MAX_NAME - 1] + "…"
    return name


def _tab_cell_width(name: str, dirty: bool) -> int:
    """Return the number of terminal cells occupied by one rendered tab."""
    return _PAD + len(_truncate(name)) + len(_CLOSE) + _PAD + len(_SEP)


# ---------------------------------------------------------------------------
# WrappingTabBar
# ---------------------------------------------------------------------------

class WrappingTabBar(Widget):
    """Multi-row tab strip that wraps when tabs exceed the panel width.

    Emits TabActivated / TabCloseRequested messages; EditorPanel handles them.
    """

    can_focus = False

    class TabActivated(Message):
        def __init__(self, pane_id: str) -> None:
            self.pane_id = pane_id
            super().__init__()

    class TabCloseRequested(Message):
        def __init__(self, pane_id: str) -> None:
            self.pane_id = pane_id
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tabs: list[tuple[str, str, bool]] = []   # (pane_id, display_name, dirty)
        self._active: str = ""
        self._hovered_pane: str | None = None
        # Click regions: (row, x_start, x_end, pane_id, is_close_btn)
        self._regions: list[tuple[int, int, int, str, bool]] = []

    # ------------------------------------------------------------------
    # Public API called by EditorPanel

    def set_tabs(self, tabs: list[tuple[str, str, bool]], active: str) -> None:
        self._tabs = tabs
        self._active = active
        self.refresh(layout=True)

    def set_active(self, pane_id: str) -> None:
        if self._active != pane_id:
            self._active = pane_id
            self.refresh()

    # ------------------------------------------------------------------
    # Layout

    def _pack_rows(self, width: int) -> list[list[tuple[str, str, bool]]]:
        rows: list[list[tuple[str, str, bool]]] = [[]]
        x = 0
        for entry in self._tabs:
            pane_id, name, dirty = entry
            w = _tab_cell_width(name, dirty)
            if x + w > width and rows[-1]:
                rows.append([])
                x = 0
            rows[-1].append(entry)
            x += w
        return rows if rows[0] else [[]]

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        rows = self._pack_rows(width or container.width or 80)
        return max(1, len(rows))

    # ------------------------------------------------------------------
    # Render

    def render(self) -> Text:
        width = self.size.width or 80
        rows = self._pack_rows(width)
        self._regions = []

        combined = Text()
        for row_idx, row_tabs in enumerate(rows):
            if row_idx > 0:
                combined.append("\n")
            x = 0
            for pane_id, name, dirty in row_tabs:
                is_active  = pane_id == self._active
                is_hovered = pane_id == self._hovered_pane

                if is_active:
                    bg, fg, bold = "#1f2d3d", "#e6edf3", True
                elif is_hovered:
                    bg, fg, bold = "#161b22", "#c9d1d9", False
                else:
                    bg, fg, bold = "#0d1117", "#8b949e", False

                # Dirty files get orange label regardless of active/hover state
                name_fg = "#e3a04f" if dirty else fg

                tab_style   = ("bold " if bold else "") + f"{fg} on {bg}"
                name_style  = ("bold " if bold else "") + f"{name_fg} on {bg}"
                close_style = f"dim #6e7681 on {bg}"
                sep_style   = "#21262d on #0d1117"

                display_name = _truncate(name)
                pad_left     = " " * _PAD
                pad_right    = " " * _PAD

                tab_start   = x
                close_start = x + len(pad_left) + len(display_name)
                close_end   = close_start + len(_CLOSE)
                tab_end     = close_end + len(pad_right) + len(_SEP)

                combined.append(pad_left,    style=tab_style)
                combined.append(display_name, style=name_style)
                combined.append(_CLOSE,      style=close_style)
                combined.append(pad_right,   style=tab_style)
                combined.append(_SEP,        style=sep_style)
                x = tab_end

                self._regions.append((row_idx, tab_start, close_start, pane_id, False))
                self._regions.append((row_idx, close_start, close_end, pane_id, True))

        return combined

    # ------------------------------------------------------------------
    # Events

    def _region_at(self, ex: int, ey: int) -> tuple[str, bool] | None:
        for row, x0, x1, pane_id, is_close in self._regions:
            if ey == row and x0 <= ex < x1:
                return pane_id, is_close
        return None

    def on_mouse_move(self, event: events.MouseMove) -> None:
        hit = self._region_at(event.x, event.y)
        new_hovered = hit[0] if hit else None
        if new_hovered != self._hovered_pane:
            self._hovered_pane = new_hovered
            self.refresh()

    def on_leave(self, event: events.Leave) -> None:
        if self._hovered_pane is not None:
            self._hovered_pane = None
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        hit = self._region_at(event.x, event.y)
        if hit is None:
            return
        pane_id, is_close = hit
        event.stop()
        if is_close:
            self.post_message(self.TabCloseRequested(pane_id))
        else:
            self.post_message(self.TabActivated(pane_id))


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

SCALA_HIGHLIGHT_QUERY = """
[(comment) (block_comment)] @comment
[(string) (interpolated_string)] @string
[(integer_literal) (floating_point_literal)] @number
[
  "package"
  "import"
  "class"
  "object"
  "trait"
  "extends"
  "def"
  "val"
  "var"
  "if"
  "else"
  "match"
  "case"
  "for"
  "yield"
  "while"
  "do"
  "try"
  "catch"
  "finally"
  "throw"
  "return"
  "new"
  "override"
  "implicit"
  "given"
  "using"
  "enum"
  "with"
  "sealed"
  "final"
  "lazy"
  "private"
  "protected"
  "abstract"
] @keyword
(boolean_literal) @constant.builtin
(null_literal) @constant.builtin
(function_definition name: (identifier) @function)
(call_expression function: (identifier) @function)
(call_expression function: (field_expression field: (identifier) @function.method))
(type_identifier) @type
(class_definition name: (identifier) @type)
(object_definition name: (identifier) @type)
(parameter name: (identifier) @variable.parameter)
(class_parameter name: (identifier) @variable.parameter)
(field_expression field: (identifier) @property)
(operator_identifier) @operator
(wildcard) @variable.builtin
"""


def detect_language(path: Path) -> str | None:
    suffix = path.suffix.lower()
    mapping = {
        ".py":    "python",
        ".sql":   "sql",
        ".md":    "markdown",
        ".sh":    "bash",
        ".bash":  "bash",
        ".zsh":   "bash",
        ".json":  "json",
        ".toml":  "toml",
        ".yaml":  "yaml",
        ".yml":   "yaml",
        ".csv":   None,
        ".tsv":   None,
        ".scala": "scala",
        ".sc":    "scala",
        ".sbt":   "scala",
    }
    return mapping.get(suffix)


def _apply_language(text_area: TextArea, language: str | None) -> None:
    if language == "scala":
        try:
            from tree_sitter_languages import get_language

            text_area.register_language(get_language("scala"), SCALA_HIGHLIGHT_QUERY)
        except Exception:
            language = "java"

    if language is None:
        return

    try:
        text_area.language = language
    except Exception:
        pass


def build_editor_theme() -> TextAreaTheme:
    base = TextAreaTheme.get_builtin_theme("vscode_dark")
    if base is None:
        return TextAreaTheme(
            name="tuide_code",
            syntax_styles={
                "keyword":  Style(color="#f7c96a", bold=True),
                "string":   Style(color="#98c379"),
                "comment":  Style(color="#6a9955", italic=True),
                "function": Style(color="#61afef"),
                "type":     Style(color="#e5c07b", bold=True),
                "number":   Style(color="#d19a66"),
            },
        )

    syntax_styles = dict(base.syntax_styles)
    syntax_styles.update({
        "keyword":            Style(color="#f7c96a", bold=True),
        "keyword.function":   Style(color="#f7c96a", bold=True),
        "string":             Style(color="#98c379"),
        "comment":            Style(color="#6a9955", italic=True),
        "function":           Style(color="#61afef", bold=True),
        "function.method":    Style(color="#7ec7ff"),
        "function.builtin":   Style(color="#56b6c2"),
        "type":               Style(color="#e5c07b", bold=True),
        "type.builtin":       Style(color="#e5c07b", bold=True),
        "constructor":        Style(color="#d19a66", bold=True),
        "constant.builtin":   Style(color="#d19a66", bold=True),
        "number":             Style(color="#d19a66"),
        "operator":           Style(color="#c8d3df"),
        "property":           Style(color="#c678dd"),
        "variable.parameter": Style(color="#e06c75", italic=True),
        "variable.builtin":   Style(color="#56b6c2"),
    })
    return replace(
        base,
        name="tuide_code",
        base_style=Style(color="#cccccc", bgcolor="#0d1117"),
        gutter_style=Style(color="#6e7681", bgcolor="#0d1117"),
        cursor_line_style=Style(bgcolor="#2d333b"),
        cursor_line_gutter_style=Style(color="#e6edf3", bgcolor="#2d333b"),
        selection_style=Style(bgcolor="#1d3557"),
        syntax_styles=syntax_styles,
    )


def build_code_editor(text: str, path: Path, pane_id: str) -> TextArea:
    editor = TextArea(
        text=text,
        language=None,
        id=f"editor-{pane_id}",
        soft_wrap=False,
        tab_behavior="indent",
    )
    _apply_language(editor, detect_language(path))
    try:
        editor.register_theme(build_editor_theme())
        editor.theme = "tuide_code"
    except Exception:
        pass
    try:
        editor.match_cursor_bracket = True
    except Exception:
        pass
    try:
        editor.cursor_blink = False
    except Exception:
        pass
    editor.show_line_numbers = True
    return editor


# ---------------------------------------------------------------------------
# EditorPanel — plain Vertical + manual display toggling + WrappingTabBar
# ---------------------------------------------------------------------------

class EditorPanel(Vertical):
    """Tabbed editor area that can open files from the workspace tree."""

    DEFAULT_CLASSES = "panel-frame"
    can_focus = True

    def __init__(self) -> None:
        super().__init__(id="editor-panel")
        self.documents: dict[str, OpenDocument] = {}
        self._virtual_tab_labels: dict[str, str] = {}
        self._current_pane: str = ""

    def compose(self) -> ComposeResult:
        yield WrappingTabBar(id="editor-tab-bar")
        yield Vertical(id="editor-content")

    def on_mount(self) -> None:
        self._sync_tab_bar()

    # ------------------------------------------------------------------
    # Pane switching

    def _show_pane(self, pane_id: str) -> None:
        """Show exactly one child of #editor-content, hide all others."""
        container = self.query_one("#editor-content")
        for child in container.children:
            child.display = child.id == pane_id
        self._current_pane = pane_id

    @property
    def tab_bar(self) -> WrappingTabBar:
        return self.query_one(WrappingTabBar)

    # ------------------------------------------------------------------
    # Tab-bar sync

    def _sync_tab_bar(self) -> None:
        try:
            bar = self.query_one(WrappingTabBar)
        except Exception:
            return
        container = self.query_one("#editor-content")
        tabs: list[tuple[str, str, bool]] = []
        for child in container.children:
            pane_id = child.id
            doc = self.documents.get(pane_id)
            if doc is not None:
                tabs.append((pane_id, doc.path.name, doc.dirty))
            else:
                label = self._virtual_tab_labels.get(pane_id, pane_id)
                tabs.append((pane_id, label, False))
        bar.set_tabs(tabs, self._current_pane)

    @on(WrappingTabBar.TabActivated)
    def _on_bar_tab_activated(self, event: WrappingTabBar.TabActivated) -> None:
        self._show_pane(event.pane_id)
        self._sync_tab_bar()
        doc = self.documents.get(event.pane_id)
        if doc is not None:
            try:
                self.query_one(f"#editor-{doc.pane_id}", TextArea).focus()
            except Exception:
                pass

    @on(WrappingTabBar.TabCloseRequested)
    def _on_bar_tab_close_requested(self, event: WrappingTabBar.TabCloseRequested) -> None:
        self.run_worker(self._close_pane_by_id(event.pane_id), exclusive=False)

    # ------------------------------------------------------------------
    # Properties

    @property
    def active_pane_id(self) -> str:
        return self._current_pane or ""

    @property
    def active_document(self) -> OpenDocument | None:
        return self.documents.get(self.active_pane_id)

    @property
    def active_path(self) -> Path | None:
        doc = self.active_document
        return doc.path if doc is not None else None

    @property
    def active_text_area(self) -> TextArea | None:
        doc = self.active_document
        if doc is None:
            return None
        try:
            return self.query_one(f"#editor-{doc.pane_id}", TextArea)
        except Exception:
            return None

    def active_cursor(self) -> tuple[int, int] | None:
        editor = self.active_text_area
        if editor is None:
            return None
        row, col = editor.cursor_location
        return row + 1, col + 1

    @property
    def active_text(self) -> str | None:
        editor = self.active_text_area
        return editor.text if editor is not None else None

    def find_in_active_file(self, query: str) -> list[str]:
        editor = self.active_text_area
        path = self.active_path
        if editor is None or path is None or not query:
            return []
        matches: list[str] = []
        for line_number, line in enumerate(editor.text.splitlines(), start=1):
            if query not in line:
                continue
            matches.append(f"{path}:{line_number}: {line.strip()}")
        return matches

    @property
    def dirty_documents(self) -> list[OpenDocument]:
        return [doc for doc in self.documents.values() if doc.dirty]

    @property
    def dirty_count(self) -> int:
        return len(self.dirty_documents)

    def has_unsaved_changes(self) -> bool:
        return self.dirty_count > 0

    # ------------------------------------------------------------------
    # File operations

    async def open_file(self, path: Path, git_head_text: str | None = None) -> None:
        pane_id = self._pane_id_for_path(path)
        content_area = self.query_one("#editor-content")

        if pane_id not in [c.id for c in content_area.children]:
            content = path.read_text(encoding="utf-8", errors="replace")
            editor = build_code_editor(content, path, pane_id)
            container = Vertical(editor, id=pane_id, classes="editor-pane")
            await content_area.mount(container)
            doc = OpenDocument(path=path, pane_id=pane_id, saved_text=content, git_head_text=git_head_text)
            doc.dirty = git_head_text is not None and content != git_head_text
            self.documents[pane_id] = doc

        self._show_pane(pane_id)
        self._sync_tab_bar()
        ta = self.active_text_area
        if ta is not None:
            ta.focus()

    def reload_file(self, path: Path) -> None:
        """Reload a file from disk into its open TextArea and reset dirty state."""
        pane_id = self._pane_id_for_path(path)
        doc = self.documents.get(pane_id)
        if doc is None:
            return
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        try:
            ta = self.query_one(f"#editor-{pane_id}", TextArea)
            ta.load_text(content)
        except Exception:
            pass
        doc.dirty = doc.git_head_text is not None and content != doc.git_head_text
        self._sync_tab_bar()

    def mark_all_as_clean(self) -> None:
        """After a commit, update git_head_text for every open doc to its current content."""
        for pane_id, doc in self.documents.items():
            try:
                ta = self.query_one(f"#editor-{pane_id}", TextArea)
                current = ta.text
            except Exception:
                continue
            doc.git_head_text = current
            doc.dirty = False
        self._sync_tab_bar()

    async def close_active_tab(self) -> Path | None:
        active_id = self._current_pane
        if not active_id:
            return None
        doc = self.documents.pop(active_id, None)
        self._virtual_tab_labels.pop(active_id, None)
        content_area = self.query_one("#editor-content")
        try:
            child = content_area.query_one(f"#{active_id}")
            await child.remove()
        except Exception:
            pass
        if content_area.children:
            self._show_pane(content_area.children[0].id)
        else:
            self._current_pane = ""
        self._sync_tab_bar()
        return doc.path if doc else None

    async def open_readonly_tab(self, title: str, text: str, *, language: str | None = None) -> str:
        pane_id = self._pane_id_for_virtual_title(title)
        content_area = self.query_one("#editor-content")

        if pane_id not in [c.id for c in content_area.children]:
            viewer = TextArea(text=text, language=None, read_only=True, id=f"viewer-{pane_id}")
            _apply_language(viewer, language)
            viewer.show_line_numbers = True
            container = Vertical(viewer, id=pane_id, classes="editor-pane")
            await content_area.mount(container)
            self._virtual_tab_labels[pane_id] = title

        self._show_pane(pane_id)
        self._sync_tab_bar()
        return pane_id

    async def open_result_tab(self, title: str, text: str) -> str:
        pane_id = self._pane_id_for_virtual_title(title)
        content_area = self.query_one("#editor-content")

        if pane_id not in [c.id for c in content_area.children]:
            container = Vertical(Static(text, classes="panel-body"), id=pane_id, classes="editor-pane")
            await content_area.mount(container)
            self._virtual_tab_labels[pane_id] = title

        self._show_pane(pane_id)
        self._sync_tab_bar()
        return pane_id

    async def open_widget_tab(
        self,
        title: str,
        widget: Widget,
        *,
        always_replace: bool = False,
    ) -> str:
        pane_id = self._pane_id_for_virtual_title(title)
        content_area = self.query_one("#editor-content")

        if always_replace:
            try:
                old = content_area.query_one(f"#{pane_id}")
                await old.remove()
                self._virtual_tab_labels.pop(pane_id, None)
            except Exception:
                pass

        if pane_id not in [c.id for c in content_area.children]:
            container = Vertical(widget, id=pane_id, classes="editor-pane")
            await content_area.mount(container)
            self._virtual_tab_labels[pane_id] = title

        self._show_pane(pane_id)
        self._sync_tab_bar()
        return pane_id

    async def open_diff_tab(
        self,
        title: str,
        left_title: str,
        left_text: str,
        right_title: str,
        right_text: str,
    ) -> str:
        pane_id = self._pane_id_for_virtual_title(title)
        content_area = self.query_one("#editor-content")

        if pane_id not in [c.id for c in content_area.children]:
            diff = DiffView(left_title, left_text, right_title, right_text)
            container = Vertical(diff, id=pane_id, classes="editor-pane")
            await content_area.mount(container)
            self._virtual_tab_labels[pane_id] = title

        self._show_pane(pane_id)
        self._sync_tab_bar()
        return pane_id

    async def open_welcome_tab(self, project_name: str, readme_text: str | None) -> None:
        """Open (or focus) the welcome tab for the given project."""
        pane_id = "welcome-pane"
        content_area = self.query_one("#editor-content")

        if pane_id in [c.id for c in content_area.children]:
            self._show_pane(pane_id)
            self._sync_tab_bar()
            return

        if readme_text:
            viewer = TextArea(text=readme_text, language=None, read_only=True, id=f"viewer-{pane_id}")
            _apply_language(viewer, "markdown")
            viewer.show_line_numbers = False
            content = viewer
        else:
            content = Label(
                f"{project_name}\n\nOpen a file from the workspace tree on the left.",
                classes="editor-welcome",
            )

        container = Vertical(content, id=pane_id, classes="editor-pane")
        await content_area.mount(container)
        self._virtual_tab_labels[pane_id] = project_name
        self._show_pane(pane_id)
        self._sync_tab_bar()

    async def _close_pane_by_id(self, pane_id: str) -> None:
        self.documents.pop(pane_id, None)
        self._virtual_tab_labels.pop(pane_id, None)
        content_area = self.query_one("#editor-content")
        was_active = self._current_pane == pane_id
        try:
            child = content_area.query_one(f"#{pane_id}")
            await child.remove()
        except Exception:
            pass
        if was_active:
            if content_area.children:
                self._show_pane(content_area.children[0].id)
            else:
                self._current_pane = ""
        self._sync_tab_bar()

    # ------------------------------------------------------------------
    # Dirty tracking

    @on(TextArea.Changed)
    def handle_text_change(self, event: TextArea.Changed) -> None:
        pane_id = event.text_area.id.removeprefix("editor-")
        doc = self.documents.get(pane_id)
        if doc is None:
            return
        current_text = event.text_area.text
        # Auto-save every change immediately
        try:
            doc.path.write_text(current_text, encoding="utf-8")
        except Exception:
            pass
        # Dirty = differs from git HEAD (not from saved state)
        now_dirty = current_text != doc.git_head_text if doc.git_head_text is not None else False
        if now_dirty == doc.dirty:
            return
        doc.dirty = now_dirty
        self._sync_tab_bar()

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _pane_id_for_path(path: Path) -> str:
        return "file-" + str(path).replace("\\", "-").replace("/", "-").replace(":", "").replace(".", "-")

    @staticmethod
    def _pane_id_for_virtual_title(title: str) -> str:
        return "virtual-" + title.lower().replace(" ", "-").replace("/", "-").replace(":", "").replace(".", "-")
