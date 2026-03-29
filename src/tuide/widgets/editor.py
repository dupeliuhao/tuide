"""Editor widgets for the Linux-first shell."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.containers import Vertical
from textual.widgets import Label, Static, TabPane, TabbedContent, TextArea

from tuide.models import OpenDocument
from tuide.widgets.diffview import DiffView


def detect_language(path: Path) -> str | None:
    """Return a best-effort TextArea language name for a file path."""
    suffix = path.suffix.lower()
    mapping = {
        ".py": "python",
        ".sql": "sql",
        ".md": "markdown",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".json": "json",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".csv": None,
        ".tsv": None,
        ".scala": None,
        ".sc": None,
        ".sbt": None,
    }
    return mapping.get(suffix)


class EditorPanel(Vertical):
    """Tabbed editor area that can open files from the workspace tree."""

    DEFAULT_CLASSES = "panel-frame"
    can_focus = True

    def __init__(self) -> None:
        super().__init__(id="editor-panel")
        self.documents: dict[str, OpenDocument] = {}

    def compose(self):
        yield Label("Editor", classes="panel-title")
        yield Label("Open a file from the workspace tree.", classes="panel-subtitle", id="editor-subtitle")
        with TabbedContent(id="editor-tabs"):
            with TabPane("Welcome", id="welcome-tab"):
                yield Label(
                    "Linux-first tuide shell\n\nSelect a file on the left to open it here.",
                    classes="panel-body",
                    id="welcome-copy",
                )

    @property
    def tabbed_content(self) -> TabbedContent:
        """Return the internal tabbed content widget."""
        return self.query_one("#editor-tabs", TabbedContent)

    async def open_file(self, path: Path) -> None:
        """Open a file in a new tab or focus an existing tab."""
        pane_id = self._pane_id_for_path(path)
        tabbed = self.tabbed_content

        try:
            tabbed.get_pane(pane_id)
        except Exception:
            content = path.read_text(encoding="utf-8", errors="replace")
            editor = TextArea(
                text=content,
                language=detect_language(path),
                id=f"editor-{pane_id}",
                soft_wrap=False,
                tab_behavior="indent",
            )
            editor.show_line_numbers = True
            pane = TabPane(path.name, editor, id=pane_id)
            await tabbed.add_pane(pane)
            self.documents[pane_id] = OpenDocument(path=path, pane_id=pane_id)
        tabbed.active = pane_id

        subtitle = self.query_one("#editor-subtitle", Label)
        subtitle.update(str(path))
        editor = self.active_text_area
        if editor is not None:
            editor.focus()

    @property
    def active_pane_id(self) -> str:
        """Return the active pane identifier."""
        return self.tabbed_content.active

    @property
    def active_document(self) -> OpenDocument | None:
        """Return the active open document, if any."""
        return self.documents.get(self.active_pane_id)

    @property
    def active_path(self) -> Path | None:
        """Return the active file path, if any."""
        document = self.active_document
        return document.path if document is not None else None

    @property
    def active_text_area(self) -> TextArea | None:
        """Return the active text area when a file tab is selected."""
        document = self.active_document
        if document is None:
            return None
        return self.query_one(f"#editor-{document.pane_id}", TextArea)

    def active_cursor(self) -> tuple[int, int] | None:
        """Return the current cursor position as 1-based line and column."""
        editor = self.active_text_area
        if editor is None:
            return None
        row, column = editor.cursor_location
        return row + 1, column + 1

    def find_in_active_file(self, query: str) -> list[str]:
        """Return formatted matches from the active editor."""
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
        """Return all currently dirty open documents."""
        return [document for document in self.documents.values() if document.dirty]

    @property
    def dirty_count(self) -> int:
        """Return the number of dirty open documents."""
        return len(self.dirty_documents)

    def save_active_file(self) -> Path | None:
        """Save the active file tab to disk."""
        document = self.active_document
        editor = self.active_text_area
        if document is None or editor is None:
            return None

        document.path.write_text(editor.text, encoding="utf-8")
        document.dirty = False
        self._update_tab_title(document)
        return document.path

    async def close_active_tab(self) -> Path | None:
        """Close the active file tab if one is selected."""
        document = self.active_document
        if document is None:
            return None

        await self.tabbed_content.remove_pane(document.pane_id)
        self.documents.pop(document.pane_id, None)

        subtitle = self.query_one("#editor-subtitle", Label)
        next_document = self.active_document
        subtitle.update(str(next_document.path) if next_document else "Open a file from the workspace tree.")
        return document.path

    async def open_readonly_tab(self, title: str, text: str, *, language: str | None = None) -> str:
        """Open a read-only content tab."""
        pane_id = self._pane_id_for_virtual_title(title)
        tabbed = self.tabbed_content

        try:
            tabbed.get_pane(pane_id)
        except Exception:
            viewer = TextArea(text=text, language=language, read_only=True, id=f"viewer-{pane_id}")
            viewer.show_line_numbers = True
            pane = TabPane(title, viewer, id=pane_id)
            await tabbed.add_pane(pane)
        tabbed.active = pane_id

        subtitle = self.query_one("#editor-subtitle", Label)
        subtitle.update(title)
        return pane_id

    async def open_result_tab(self, title: str, text: str) -> str:
        """Open a lightweight result tab."""
        pane_id = self._pane_id_for_virtual_title(title)
        tabbed = self.tabbed_content
        try:
            tabbed.get_pane(pane_id)
        except Exception:
            pane = TabPane(title, Static(text, classes="panel-body"), id=pane_id)
            await tabbed.add_pane(pane)
        tabbed.active = pane_id
        subtitle = self.query_one("#editor-subtitle", Label)
        subtitle.update(title)
        return pane_id

    async def open_diff_tab(
        self,
        title: str,
        left_title: str,
        left_text: str,
        right_title: str,
        right_text: str,
    ) -> str:
        """Open a side-by-side read-only diff tab."""
        pane_id = self._pane_id_for_virtual_title(title)
        tabbed = self.tabbed_content
        try:
            tabbed.get_pane(pane_id)
        except Exception:
            pane = TabPane(title, DiffView(left_title, left_text, right_title, right_text), id=pane_id)
            await tabbed.add_pane(pane)
        tabbed.active = pane_id
        subtitle = self.query_one("#editor-subtitle", Label)
        subtitle.update(title)
        return pane_id

    def has_unsaved_changes(self) -> bool:
        """Return whether any open document is dirty."""
        return self.dirty_count > 0

    @on(TextArea.Changed)
    def handle_text_change(self, event: TextArea.Changed) -> None:
        """Track dirty state for open documents."""
        pane_id = event.text_area.id.removeprefix("editor-")
        document = self.documents.get(pane_id)
        if document is None or document.dirty:
            return
        document.dirty = True
        self._update_tab_title(document)

    def _update_tab_title(self, document: OpenDocument) -> None:
        """Refresh a tab title to reflect dirty state."""
        pane = self.tabbed_content.get_pane(document.pane_id)
        pane.title = f"* {document.path.name}" if document.dirty else document.path.name

    @staticmethod
    def _pane_id_for_path(path: Path) -> str:
        """Return a stable tab id for a file path."""
        return "file-" + str(path).replace("\\", "-").replace("/", "-").replace(":", "").replace(".", "-")

    @staticmethod
    def _pane_id_for_virtual_title(title: str) -> str:
        """Return a stable pane id for a virtual tab."""
        return "virtual-" + title.lower().replace(" ", "-").replace("/", "-").replace(":", "")
