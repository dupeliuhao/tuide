"""Core shell panels for the Linux-first scaffold."""

from __future__ import annotations

from pathlib import Path

from textual.containers import Vertical
from textual.widgets import DirectoryTree, Label, Select, Static

from tuide.models import WorkspaceState


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
        root_label = self.primary_root.name or str(self.primary_root)
        title = f"Workspace ({len(self.workspace_state.roots)})"
        subtitle = f"Active root: {root_label}"
        yield Label(title, classes="panel-title")
        yield Label(subtitle, classes="panel-subtitle")
        root_summary = "\n".join(f"- {root}" for root in self.workspace_state.roots[:5])
        yield Static(root_summary, classes="workspace-summary", id="workspace-roots")
        yield Select(
            [(str(root), str(root)) for root in self.workspace_state.roots],
            value=str(self.primary_root),
            id="workspace-root-select",
            prompt="Active workspace root",
            allow_blank=False,
        )
        yield DirectoryTree(str(self.primary_root), id="workspace-tree")

    def set_active_root(self, root: Path) -> None:
        """Switch the active root shown by the tree."""
        tree = self.query_one("#workspace-tree", DirectoryTree)
        tree.path = root
        subtitle = self.query_one(".panel-subtitle", Label)
        subtitle.update(f"Active root: {root.name or root}")

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

        summary = self.query_one("#workspace-roots", Static)
        root_summary = "\n".join(f"- {root}" for root in workspace_state.roots[:5])
        summary.update(root_summary)
