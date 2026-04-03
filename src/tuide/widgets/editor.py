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
from textual.widgets import ContentSwitcher, Label, Static, TextArea
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
    return _PAD + (2 if dirty else 0) + len(_truncate(name)) + len(_CLOSE) + _PAD + len(_SEP)


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

                tab_style   = ("bold " if bold else "") + f"{fg} on {bg}"
                close_style = f"dim #6e7681 on {bg}"
                sep_style   = "#21262d on #0d1117"

                dirty_mark   = "* " if dirty else ""
                display_name = _truncate(name)
                label_part   = " " * _PAD + dirty_mark + display_name
                pad_right    = " " * _PAD

                tab_start   = x
                close_start = x + len(label_part)
                close_end   = close_start + len(_CLOSE)
                tab_end     = close_end + _PAD + len(_SEP)

                combined.append(label_part, style=tab_style)
                combined.append(_CLOSE,     style=close_style)
                combined.append(pad_right,  style=tab_style)
                combined.append(_SEP,       style=sep_style)
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
        ".scala": None,
        ".sc":    None,
        ".sbt":   None,
    }
    return mapping.get(suffix)


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
        language=detect_language(path),
        id=f"editor-{pane_id}",
        soft_wrap=False,
        tab_behavior="indent",
    )
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
# EditorPanel — uses ContentSwitcher (not TabbedContent) + WrappingTabBar
# ---------------------------------------------------------------------------

class EditorPanel(Vertical):
    """Tabbed editor area that can open files from the workspace tree."""

    DEFAULT_CLASSES = "panel-frame"
    can_focus = True

    def __init__(self) -> None:
        super().__init__(id="editor-panel")
        self.documents: dict[str, OpenDocument] = {}
        self._virtual_tab_labels: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield WrappingTabBar(id="editor-tab-bar")
        with ContentSwitcher(id="editor-content", initial="welcome-pane"):
            with Vertical(id="welcome-pane"):
                yield Label(
                    "tuide\n\nOpen a file from the workspace tree on the left.",
                    classes="editor-welcome",
                    id="welcome-copy",
                )

    def on_mount(self) -> None:
        self._sync_tab_bar()

    # ------------------------------------------------------------------
    # Tab-bar sync

    @property
    def content_switcher(self) -> ContentSwitcher:
        return self.query_one("#editor-content", ContentSwitcher)

    @property
    def tab_bar(self) -> WrappingTabBar:
        return self.query_one(WrappingTabBar)

    def _sync_tab_bar(self) -> None:
        try:
            bar = self.query_one(WrappingTabBar)
        except Exception:
            return
        switcher = self.content_switcher
        tabs: list[tuple[str, str, bool]] = []
        for child in switcher.children:
            pane_id = child.id
            doc = self.documents.get(pane_id)
            if doc is not None:
                tabs.append((pane_id, doc.path.name, doc.dirty))
            elif pane_id == "welcome-pane":
                tabs.append((pane_id, "Welcome", False))
            else:
                label = self._virtual_tab_labels.get(pane_id, pane_id)
                tabs.append((pane_id, label, False))
        bar.set_tabs(tabs, switcher.current or "")

    @on(WrappingTabBar.TabActivated)
    def _on_bar_tab_activated(self, event: WrappingTabBar.TabActivated) -> None:
        self.content_switcher.current = event.pane_id
        self._sync_tab_bar()
        doc = self.documents.get(event.pane_id)
        if doc is not None:
            try:
                self.query_one(f"#editor-{doc.pane_id}", TextArea).focus()
            except Exception:
                pass

    @on(WrappingTabBar.TabCloseRequested)
    def _on_bar_tab_close_requested(self, event: WrappingTabBar.TabCloseRequested) -> None:
        if event.pane_id == "welcome-pane":
            return
        self.run_worker(self._close_pane_by_id(event.pane_id), exclusive=False)

    # ------------------------------------------------------------------
    # Properties

    @property
    def active_pane_id(self) -> str:
        return self.content_switcher.current or ""

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

    async def open_file(self, path: Path) -> None:
        pane_id = self._pane_id_for_path(path)
        switcher = self.content_switcher

        if pane_id not in [c.id for c in switcher.children]:
            content = path.read_text(encoding="utf-8", errors="replace")
            editor = build_code_editor(content, path, pane_id)
            container = Vertical(editor, id=pane_id, classes="editor-pane")
            await switcher.mount(container)
            self.documents[pane_id] = OpenDocument(path=path, pane_id=pane_id, saved_text=content)

        switcher.current = pane_id
        self._sync_tab_bar()
        ta = self.active_text_area
        if ta is not None:
            ta.focus()

    def save_active_file(self) -> Path | None:
        doc = self.active_document
        editor = self.active_text_area
        if doc is None or editor is None:
            return None
        doc.path.write_text(editor.text, encoding="utf-8")
        doc.dirty = False
        doc.saved_text = editor.text
        self._sync_tab_bar()
        return doc.path

    async def close_active_tab(self) -> Path | None:
        switcher = self.content_switcher
        active_id = switcher.current
        if not active_id or active_id == "welcome-pane":
            return None
        doc = self.documents.pop(active_id, None)
        self._virtual_tab_labels.pop(active_id, None)
        try:
            child = switcher.query_one(f"#{active_id}")
            await child.remove()
        except Exception:
            pass
        # Activate the first remaining child
        if switcher.children:
            switcher.current = switcher.children[0].id
        self._sync_tab_bar()
        return doc.path if doc else None

    async def open_readonly_tab(self, title: str, text: str, *, language: str | None = None) -> str:
        pane_id = self._pane_id_for_virtual_title(title)
        switcher = self.content_switcher

        if pane_id not in [c.id for c in switcher.children]:
            viewer = TextArea(text=text, language=language, read_only=True, id=f"viewer-{pane_id}")
            viewer.show_line_numbers = True
            container = Vertical(viewer, id=pane_id, classes="editor-pane")
            await switcher.mount(container)
            self._virtual_tab_labels[pane_id] = title

        switcher.current = pane_id
        self._sync_tab_bar()
        return pane_id

    async def open_result_tab(self, title: str, text: str) -> str:
        pane_id = self._pane_id_for_virtual_title(title)
        switcher = self.content_switcher

        if pane_id not in [c.id for c in switcher.children]:
            container = Vertical(Static(text, classes="panel-body"), id=pane_id, classes="editor-pane")
            await switcher.mount(container)
            self._virtual_tab_labels[pane_id] = title

        switcher.current = pane_id
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
        switcher = self.content_switcher

        if always_replace:
            try:
                old = switcher.query_one(f"#{pane_id}")
                await old.remove()
                self._virtual_tab_labels.pop(pane_id, None)
            except Exception:
                pass

        if pane_id not in [c.id for c in switcher.children]:
            container = Vertical(widget, id=pane_id, classes="editor-pane")
            await switcher.mount(container)
            self._virtual_tab_labels[pane_id] = title

        switcher.current = pane_id
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
        switcher = self.content_switcher

        if pane_id not in [c.id for c in switcher.children]:
            diff = DiffView(left_title, left_text, right_title, right_text)
            container = Vertical(diff, id=pane_id, classes="editor-pane")
            await switcher.mount(container)
            self._virtual_tab_labels[pane_id] = title

        switcher.current = pane_id
        self._sync_tab_bar()
        return pane_id

    async def _close_pane_by_id(self, pane_id: str) -> None:
        self.documents.pop(pane_id, None)
        self._virtual_tab_labels.pop(pane_id, None)
        switcher = self.content_switcher
        was_active = switcher.current == pane_id
        try:
            child = switcher.query_one(f"#{pane_id}")
            await child.remove()
        except Exception:
            pass
        if was_active and switcher.children:
            switcher.current = switcher.children[0].id
        self._sync_tab_bar()

    # ------------------------------------------------------------------
    # Dirty tracking

    @on(TextArea.Changed)
    def handle_text_change(self, event: TextArea.Changed) -> None:
        pane_id = event.text_area.id.removeprefix("editor-")
        doc = self.documents.get(pane_id)
        if doc is None:
            return
        now_dirty = event.text_area.text != doc.saved_text
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
