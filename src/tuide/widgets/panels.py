"""Core shell panels for the Linux-first scaffold."""

from __future__ import annotations

from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual.containers import Vertical
from textual.widgets import DirectoryTree, Label, Select, Static
from textual.widgets._directory_tree import DirEntry
from textual.widgets._tree import TreeNode

from tuide.models import WorkspaceState


_FILE_TYPE_STYLES: dict[str, Style] = {
    ".py": Style(color="#61afef"),
    ".scala": Style(color="#f7c96a"),
    ".sc": Style(color="#f7c96a"),
    ".sbt": Style(color="#e5c07b"),
    ".md": Style(color="#98c379"),
    ".json": Style(color="#d19a66"),
    ".toml": Style(color="#e5c07b"),
    ".yaml": Style(color="#56b6c2"),
    ".yml": Style(color="#56b6c2"),
    ".sql": Style(color="#c678dd"),
    ".sh": Style(color="#e06c75"),
    ".bash": Style(color="#e06c75"),
    ".zsh": Style(color="#e06c75"),
    ".txt": Style(color="#8b949e"),
}

_SPECIAL_FILE_STYLES: dict[str, Style] = {
    "dockerfile": Style(color="#58a6ff"),
    "makefile": Style(color="#e5c07b"),
}


def _file_type_style(path: Path) -> Style | None:
    special = _SPECIAL_FILE_STYLES.get(path.name.lower())
    if special is not None:
        return special
    return _FILE_TYPE_STYLES.get(path.suffix.lower())


_DIRTY_STYLE = Style(color="#f7c96a", bold=True)


class _NarrowDirectoryTree(DirectoryTree):
    """DirectoryTree with single-width ASCII icons for cross-terminal compatibility."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._dirty_paths: set[str] = set()

    def set_dirty_paths(self, paths: set[str]) -> None:
        """Update the set of repo-relative dirty file paths and refresh."""
        self._dirty_paths = paths
        self.refresh()

    def render_label(self, node: TreeNode[DirEntry], base_style: Style, style: Style) -> Text:
        node_label = node._label.copy()
        node_label.stylize(style)

        if not self.is_mounted:
            return node_label

        if node._allow_expand:
            prefix = ("▾ " if node.is_expanded else "▸ ", base_style)
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--folder", partial=True)
            )
        else:
            prefix = ("  ", base_style)
            file_style = self.get_component_rich_style("directory-tree--file", partial=True)
            path = node.data.path if node.data is not None else None
            type_style = _file_type_style(path) if path is not None else None
            if type_style is not None:
                file_style = Style.combine([file_style, type_style])
            node_label.stylize_before(file_style)

        if node_label.plain.startswith("."):
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--hidden")
            )

        dirty_marker = Text("")
        if not node._allow_expand and node.data is not None:
            node_str = str(node.data.path)
            if node_str in self._dirty_paths:
                dirty_marker = Text(" *", style=_DIRTY_STYLE)

        return Text.assemble(prefix, node_label, dirty_marker)


class PanelFrame(Vertical):
    """Reusable framed panel shell."""

    DEFAULT_CLASSES = "panel-frame"
    can_focus = True

    def __init__(self, title: str, body: str, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._title = title
        self._body = body

    def compose(self):
        yield Label(self._title, classes="panel-title")
        yield Static(self._body, classes="panel-body")


class WorkspacePanel(PanelFrame):
    """Workspace area with a styled file tree."""

    def __init__(self, workspace_state: WorkspaceState) -> None:
        super().__init__("", "", id="workspace-panel")
        self.workspace_state = workspace_state

    @property
    def primary_root(self) -> Path:
        """Return the currently displayed workspace root."""
        return self.workspace_state.roots[0]

    def compose(self):
        yield Label(f"Workspace ({len(self.workspace_state.roots)})", classes="panel-title")
        root_summary = "\n".join(f"- {root}" for root in self.workspace_state.roots[:5])
        yield Static(root_summary, classes="workspace-summary", id="workspace-roots")
        yield Select(
            [(str(root), str(root)) for root in self.workspace_state.roots],
            value=str(self.primary_root),
            id="workspace-root-select",
            prompt="Active workspace root",
            allow_blank=False,
        )
        yield _NarrowDirectoryTree(str(self.primary_root), id="workspace-tree")

    def on_mount(self) -> None:
        """Hide the root selector unless it is actually needed."""
        self._sync_root_selector_visibility()

    def set_active_root(self, root: Path) -> None:
        """Switch the active root shown by the tree."""
        tree = self.query_one("#workspace-tree", _NarrowDirectoryTree)
        tree.path = root
        select = self.query_one("#workspace-root-select", Select)
        select.value = str(root)

    def update_workspace_state(self, workspace_state: WorkspaceState) -> None:
        """Update summary widgets from a new workspace state."""
        self.workspace_state = workspace_state
        title = self.query_one(".panel-title", Label)
        title.update(f"Workspace ({len(workspace_state.roots)})")
        select = self.query_one("#workspace-root-select", Select)
        select.set_options([(str(root), str(root)) for root in workspace_state.roots])
        self.set_active_root(self.primary_root)
        self._sync_root_selector_visibility()

    def set_dirty_paths(self, paths: set[str]) -> None:
        """Pass a set of absolute path strings for files with uncommitted changes."""
        try:
            tree = self.query_one("#workspace-tree", _NarrowDirectoryTree)
            tree.set_dirty_paths(paths)
        except Exception:
            pass

    def _sync_root_selector_visibility(self) -> None:
        """Only show the root selector when multiple roots exist."""
        select = self.query_one("#workspace-root-select", Select)
        select.display = len(self.workspace_state.roots) > 1
