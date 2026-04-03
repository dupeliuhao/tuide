"""Shared data models for tuide."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class WorkspaceState:
    """Persisted workspace roots."""

    roots: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class OpenDocument:
    """Open editor document state."""

    path: Path
    pane_id: str
    dirty: bool = False
    saved_text: str = ""
    git_head_text: str | None = None


@dataclass(slots=True)
class CapabilityStatus:
    """Feature capability state shown in the status bar."""

    terminal: str = "planned"
    git: str = "unknown"
    lsp: str = "planned"


@dataclass(slots=True)
class AppConfig:
    """Persisted UI configuration."""

    workspace_width: int = 28
    terminal_width: int = 32
    default_workspace: str = ""


@dataclass(frozen=True, slots=True)
class CommandItem:
    """Command palette item."""

    id: str
    label: str
    description: str


@dataclass(frozen=True, slots=True)
class ChoiceItem:
    """Generic selectable option item."""

    id: str
    label: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class GitHistoryEntry:
    """Structured Git history entry."""

    commit: str
    date: str
    author: str
    subject: str
    unpushed: bool = False
