# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (development)
pip install -e .[linux]   # Full install with embedded terminal support
pip install -e .          # Core without textual-terminal backend

# Run
tuide                     # Launch the TUI IDE

# Lint
ruff check src/
ruff format src/

# Test
pytest
pytest tests/path/to/test.py::test_name   # Run a single test
```

Ruff is configured with `line-length = 100` and `target-version = "py311"`.

## Architecture

**tuide** is a Linux-first terminal IDE built on [Textual](https://github.com/Textualize/textual) (Python TUI framework).

### Layer overview

```
src/tuide/
├── main.py              # CLI entrypoint
├── app.py               # Root Textual App — layout, keybindings, global command dispatch
├── models.py            # Shared dataclasses (WorkspaceState, OpenDocument, AppConfig, …)
├── platform.py          # OS detection and shell defaults
├── paths.py             # platformdirs wrappers for config/workspace paths
├── widgets/             # Textual Widget subclasses (pure UI)
└── services/            # Business logic, no Textual imports
```

### `app.py` — the hub

`TuideApp` is a 3-panel Textual app: **workspace tree | editor | terminal**. It owns:
- All 24 keybindings, routed through `run_command()`
- Modal dialog lifecycle via `wait_for_screen_result()`
- Focus orchestration (panels, tabs, dialogs)
- Status bar updates

### Services (no Textual dependency)

| Service | Purpose |
|---|---|
| `GitService` | subprocess-based git (diff, history, blame, branches) |
| `LspService` | Detect availability of pyright / metals |
| `WorkspaceStore` | Persist multi-root folder list to `~/.config/tuide/workspace.toml` |
| `ConfigStore` | Persist UI config (panel widths, shell) to `~/.config/tuide/config.toml` |
| `SearchService` | File name + text search, capped at 500 results |
| `PythonSemanticService` | Fallback code intelligence when LSP is unavailable |

### Widgets

| Widget | Role |
|---|---|
| `EditorPanel` | `TabbedContent` wrapping `TextArea` per open file; writes edits through immediately and tracks git-vs-HEAD dirty state |
| `WorkspacePanel` | `DirectoryTree` with root selector |
| `TerminalPanel` | Wraps `textual-terminal`; falls back to a read-only label if unavailable |
| Dialogs (`dialogs.py`) | `ConfirmDialog`, `PromptDialog`, `CommandPaletteDialog`, `OptionPickerDialog`, `HelpDialog` — all use `EscapeDismissMixin` |
| `DiffView` | Read-only git diff/blame tab |

### Key design conventions

- **Degraded mode**: missing git, LSP, or terminal are caught at startup; affected features disable silently rather than crashing.
- **Async dialogs**: modals return values via `await wait_for_screen_result(screen)`.
- **TOML persistence**: workspace roots and config are stored as TOML; use `tomli` to read, `tomli_w` to write.
- **Python 3.11+ features used**: `match` statements, `__slots__`, `tomllib` (stdlib).

## Product logic to preserve

- **No manual save step**: editor changes are written to disk immediately on every `TextArea.Changed` event. Do not reintroduce `Ctrl+S`, save buttons, or "save file" menu actions unless the product model changes deliberately.
- **Dirty means git-dirty, not unsaved**: yellow tab styling and workspace-tree markers indicate the file differs from `git HEAD`, not that it is waiting to be written to disk.
- **Commit resets dirty state**: after a successful git commit, open documents should refresh their `git_head_text`, return to the clean styling, and lose workspace dirty markers.
- **Dismiss must always work**: modal dialogs and popups should reliably return to the main IDE view via `Esc`, `Back`, or `Cancel`. Avoid app-level button routing that can conflict with dialog-local dismissal.
- **Shortcut bar is curated, not exhaustive**: the bottom bar should only show the highest-value shortcuts. Hidden keybindings may still exist, but low-value or redundant actions should stay off the bar.

## Implementation status

See `docs/progress-checklist.md` for the current phase-by-phase status. Phase 1 (editor MVP) is complete; Phases 2–7 are partially implemented. The roadmap is in `docs/implementation-plan.md`.
