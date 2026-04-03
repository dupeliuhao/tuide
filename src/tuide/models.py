"""Shared data models for tuide."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


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


@dataclass(frozen=True, slots=True)
class GitCommandResult:
    """Structured result for git operations that can branch into follow-up UI."""

    status: Literal["success", "diverged", "conflict", "error"]
    output: str


@dataclass(frozen=True, slots=True)
class GitConflictBlock:
    """A single conflict marker block parsed from a file in the working tree."""

    index: int
    start_line: int
    end_line: int
    start_offset: int
    end_offset: int
    ours_label: str
    theirs_label: str
    ours_text: str
    theirs_text: str
    base_text: str = ""


@dataclass(frozen=True, slots=True)
class GitConflictFile:
    """Conflict state for a single file."""

    filepath: str
    blocks: list[GitConflictBlock]


@dataclass(frozen=True, slots=True)
class GitConflictState:
    """Current merge/rebase conflict session for a repository."""

    operation: Literal["merge", "rebase"]
    files: list[GitConflictFile]
