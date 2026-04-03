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


class _NarrowDirectoryTree(DirectoryTree):
    """DirectoryTree with single-width ASCII icons for cross-terminal compatibility."""

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
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--file", partial=True)
            )
            node_label.highlight_regex(
                r"\..+$",
                self.get_component_rich_style("directory-tree--extension", partial=True),
            )

        if node_label.plain.startswith("."):
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--hidden")
            )

        return Text.assemble(prefix, node_label)


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

    def _sync_root_selector_visibility(self) -> None:
        """Only show the root selector when multiple roots exist."""
        select = self.query_one("#workspace-root-select", Select)
        select.display = len(self.workspace_state.roots) > 1
