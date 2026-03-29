"""Workspace persistence helpers."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

import tomli_w

from tuide.models import WorkspaceState
from tuide.paths import default_workspace_path


class WorkspaceStore:
    """Loads and saves workspace roots."""

    def __init__(self, workspace_path: Path | None = None) -> None:
        self.workspace_path = workspace_path or default_workspace_path()

    def load(self) -> WorkspaceState:
        """Load workspace state from disk if present."""
        if not self.workspace_path.exists():
            return WorkspaceState()

        data = tomllib.loads(self.workspace_path.read_text(encoding="utf-8"))
        roots = [Path(raw).expanduser() for raw in data.get("roots", [])]
        return WorkspaceState(roots=roots)

    def save(self, state: WorkspaceState) -> None:
        """Persist workspace state to disk."""
        self.workspace_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"roots": [str(path) for path in state.roots]}
        self.workspace_path.write_text(tomli_w.dumps(payload), encoding="utf-8")

    def add_root(self, state: WorkspaceState, root: Path) -> WorkspaceState:
        """Add a workspace root if it is not already present."""
        resolved = root.expanduser().resolve()
        roots = [existing for existing in state.roots]
        if resolved not in roots:
            roots.append(resolved)
        return WorkspaceState(roots=roots)

    def remove_root(self, state: WorkspaceState, root: Path) -> WorkspaceState:
        """Remove a workspace root if present."""
        resolved = root.expanduser().resolve()
        return WorkspaceState(roots=[existing for existing in state.roots if existing != resolved])
