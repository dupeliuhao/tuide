# tuide Implementation Plan

## Summary

`tuide` is a cross-platform terminal IDE built with Python and Textual for Python- and Scala-focused development. The product goal is a keyboard-first, mouse-capable TUI that combines workspace navigation, tabbed editing, embedded terminal workflows, Git inspection, and code intelligence in a single application that works across Linux, macOS, and Windows.

This plan is intentionally phased to reduce risk. The first milestones focus on delivering a stable, usable editor shell before deeper Git, LSP, and AI behaviors are introduced. Every later subsystem should integrate through shared command routing and service abstractions rather than directly wiring widget-to-widget behavior.

## Product Principles

- Cross-platform by default: no shell-specific assumptions, use `pathlib.Path`, `subprocess` list args, and platform adapters for OS-dependent behavior.
- Standard terminal UX: `Esc` dismisses overlays, `Tab` cycles focus, `Enter` confirms, and quitting never happens accidentally.
- Keyboard and mouse parity: all major actions should be accessible from both keybindings and click interactions.
- Degraded mode over hard failure: missing Git, LSP servers, PTY support, or optional grammars should disable features gracefully and surface status to the user.
- Command-driven architecture: menu actions, keybindings, context menus, mouse gestures, and palette entries should all execute the same command handlers.

## Proposed Architecture

### Core application layers

- `app shell`: top-level `Textual` app, layout, focus orchestration, global bindings, modal/overlay management, command dispatch.
- `workspace service`: workspace file persistence, multi-root folder management, active repo detection, recent workspace handling.
- `editor service`: tab registry, dirty tracking, open/save/save-as, active buffer state, editor-view creation.
- `terminal service`: terminal widget lifecycle, shell/command configuration, restart behavior, capability detection.
- `git service`: repo discovery, branch listing, file history, blame, diff content retrieval.
- `lsp service`: per-repo language-server lifecycle, availability tracking, definition/reference requests.
- `ui widgets`: workspace tree, menu bar, splitter, tab strip, status bar, dialogs, context menus, diff/history tabs.

### Shared interfaces and decisions

- Commands should be defined centrally with stable IDs such as `file.open`, `workspace.add_folder`, `git.diff_branch`, `code.goto_definition`.
- Editor tabs should support multiple tab kinds:
  - editable file tab
  - read-only diff tab
  - read-only history/results tab
- Workspace persistence should use a TOML file under a platform-appropriate config directory via `platformdirs`.
- Each open file should resolve to a workspace root and, if present, a Git root and LSP root independently.
- Status bar state should be derived from services, not from widgets directly.

## Delivery Phases

### Phase 0: Bootstrap and feasibility spikes

Goal: remove the biggest technical unknowns before broad implementation.

- Create project scaffolding with `pyproject.toml`, package layout, dev tooling, and entrypoint.
- Add platform helpers for OS detection, config paths, shell defaults, and optional dependency checks.
- Spike these high-risk areas in isolation:
  - custom drag-to-resize splitter
  - multi-root workspace tree built from multiple `DirectoryTree` instances or a custom tree model
  - read-only side-by-side diff view using `TextArea` or a simpler synchronized viewer
  - Windows terminal embedding with `textual-terminal` plus `pywinpty`
  - Scala highlighting registration strategy
- Define the degraded-mode policy for missing dependencies:
  - no `git` executable
  - no `pyright`
  - no `metals`
  - no `pywinpty`
  - missing Scala grammar

Acceptance criteria:

- The repo boots as a runnable Textual app.
- Feasibility notes are captured for the five spike areas above.
- Dependency failures can be detected and surfaced without crashing the app.

### Phase 1: Editor shell MVP

Goal: deliver a usable core IDE shell without advanced Git or LSP features.

- Implement the 3-panel layout: workspace panel, center editor area, right terminal panel.
- Add panel toggling and keyboard-based resizing; drag-to-resize lands only after the splitter spike is accepted.
- Implement global focus and overlay rules:
  - `Esc` dismisses overlay or returns focus toward the editor
  - double `Esc` forces focus to the active editor
  - `Tab` and `Shift+Tab` cycle across major panes
- Create the tabbed editor system:
  - open file from workspace tree
  - switch tabs
  - close tab with dirty-state prompt
  - save and save-as
  - dirty indicator per tab
- Implement workspace persistence:
  - load default workspace at startup
  - add/remove folders
  - save/open workspace file
- Add the first status bar version:
  - current file
  - cursor line/column
  - detected language
  - active repo
  - feature capability badges

Acceptance criteria:

- Users can open multiple folders, open files, edit, save, close, and restore workspace state.
- Focus behavior is consistent and `Esc` never quits the app.
- The app remains usable on all three target platforms even if advanced features are absent.

### Phase 2: Unified command system and interaction framework

Goal: make all interactions consistent before adding many features.

- Introduce a central command registry and dispatcher.
- Route keybindings, menu actions, command palette entries, and context menus through that dispatcher.
- Implement reusable modal/dialog primitives:
  - confirmation dialog
  - text/path input dialog
  - searchable list picker
- Implement reusable context menu widget with keyboard and mouse behavior.
- Add the top menu bar with `File`, `Git`, and `View`.
- Add initial command palette support and keybinding help overlay.

Acceptance criteria:

- A command can be triggered identically from keyboard shortcut, menu, and command palette.
- All overlays dismiss with `Esc` and confirm with `Enter`.
- Context menus behave consistently in tree, editor, and terminal areas.

### Phase 3: Editing experience and content views

Goal: make the editor feel complete enough for day-to-day use.

- Finalize syntax highlighting support:
  - Python
  - SQL
  - Markdown
  - Shell
  - Scala
  - CSV/TSV
- Implement in-file search, quick open, and workspace-wide text search.
- Add editor context menu actions for cut/copy/paste/select all and placeholders for code intelligence and Git actions.
- Support tab types beyond editable buffers:
  - search results tab
  - file history tab
  - diff tab
- If full Scala tree-sitter registration is unstable, ship a fallback syntax mode and mark it as degraded.

Acceptance criteria:

- Users can open and edit target file types with reasonable highlighting.
- Search results and other non-file content can live as first-class tabs.
- Mouse editing and keyboard editing both work predictably.

### Phase 4: Embedded terminal integration

Goal: make terminal workflows first-class and reliable.

- Introduce a `TerminalFactory` or equivalent adapter for per-platform terminal creation.
- Default shell selection:
  - Linux/macOS: prefer user shell, fallback to `bash`
  - Windows: prefer PowerShell, fallback to `cmd`
- Add terminal restart action and capability/status reporting.
- Ensure panel resizing propagates terminal size changes correctly.
- Add terminal context menu for copy, paste, clear, and restart when supported.

Acceptance criteria:

- The terminal panel starts and restarts cleanly.
- Keyboard focus can move into and out of the terminal without trapping the user.
- Windows failure modes degrade to a simpler output/session view if PTY support is unavailable.

### Phase 5: Git inspection features

Goal: add useful Git visibility without coupling it too tightly to the editor core.

- Add repo discovery per open file.
- Implement `Diff with Branch`:
  - branch picker
  - content retrieval via `git show`
  - side-by-side diff tab
- Implement `File History`:
  - commit list tab
  - open diff tab for selected commit
- Implement `Blame` and line history after diff/history are stable.
- Keep all Git views read-only and tab-based.

Acceptance criteria:

- Users can inspect diffs and file history for files from different workspace repos.
- Git failures surface actionable messages instead of crashing tabs.
- Blame is optional and can be deferred if gutter rendering proves too fragile early on.

### Phase 6: LSP integration

Goal: deliver dependable code navigation before AI fallback.

- Add LSP capability detection at startup and on workspace changes.
- Manage per-repo server instances for Python and Scala.
- Implement:
  - go-to-definition
  - find-references
  - reference results tab
- Support invocation from keybindings, menu commands, and context menu actions.
- Surface server state in the status bar.

Acceptance criteria:

- Definition and references work for supported languages when servers are installed.
- Missing server dependencies are explained clearly.
- Multi-repo workspaces do not leak navigation requests across repo boundaries.

### Phase 7: AI fallback and workflow integration

Goal: add AI-assisted navigation only after code-intelligence entrypoints are stable.

- Introduce a code-intelligence action router:
  - prefer LSP when available
  - fallback to AI terminal workflow when unavailable
- Define the query format sent to the embedded AI session for:
  - go-to-definition fallback
  - find-references fallback
- Auto-focus or reveal the AI panel only when fallback is invoked.
- Update status indicators to show whether the current request path is `LSP` or `AI`.

Acceptance criteria:

- A code-intelligence command can succeed through either LSP or AI fallback without changing the UI contract.
- Fallback behavior is explicit to the user and does not silently replace LSP when LSP is healthy.

### Phase 8: Final polish and hardening

Goal: make the product coherent enough for regular use and future extension.

- Persist UI preferences:
  - panel sizes
  - theme
  - default workspace
  - default terminal command
  - keybinding overrides
- Add clickable status bar elements only after the base status bar proves stable.
- Review terminal-specific shortcut conflicts and ship alternative bindings where needed.
- Improve empty states, error states, and cross-platform documentation.
- Prepare a contributor guide describing architecture and extension points.

Acceptance criteria:

- The app starts with previous workspace and layout preferences restored.
- Configuration changes are documented and predictable.
- The UI remains responsive and understandable under failure conditions.

## Public Interfaces and Configuration

### Initial config file

The first config version should support:

- theme name
- default terminal command
- default workspace path
- optional keybinding overrides
- default panel sizes

Suggested storage:

- Linux/macOS: config directory from `platformdirs`
- Windows: roaming app data via `platformdirs`

### Command IDs

The first implementation should define stable command IDs for at least:

- `app.quit`
- `view.toggle_workspace`
- `view.toggle_terminal`
- `workspace.add_folder`
- `workspace.remove_folder`
- `workspace.open`
- `workspace.save_as`
- `file.open`
- `file.save`
- `file.save_as`
- `file.close`
- `search.find_in_file`
- `search.find_in_workspace`
- `search.quick_open`
- `git.diff_branch`
- `git.file_history`
- `git.blame_toggle`
- `code.goto_definition`
- `code.find_references`
- `terminal.restart`
- `help.keybindings`
- `help.command_palette`

## Risks and explicit decisions

### Highest-risk implementation areas

- Resizable splitters in Textual
- Multi-root tree UX and performance
- Read-only diff rendering with synchronized scrolling
- Windows PTY behavior
- Scala syntax-highlighting packaging
- Mapping mouse positions to editor symbols for `Ctrl+Click`
- Rendering blame information without destabilizing editing performance

### Decisions chosen for now

- Git views open as editor tabs, not as separate screens.
- LSP ships before AI fallback.
- Command routing is a first-class system, not an afterthought.
- Degraded behavior is acceptable for optional advanced features in early versions.
- Status bar click actions are postponed until the base status model is stable.

## Test Strategy

### Automated

- Unit tests for:
  - config parsing
  - workspace persistence
  - repo/root detection
  - command dispatch
  - language detection
  - diff/blame parsing helpers
- Service-level tests for Git and LSP adapters with mocked subprocess/server behavior.
- Focused widget tests where practical for command palette, pickers, and workspace operations.

### Manual cross-platform matrix

Run manual verification on:

- Linux terminal
- macOS terminal or iTerm2
- Windows Terminal with PowerShell

Verify:

- startup and shutdown
- focus navigation
- editor open/save/dirty prompts
- workspace persistence
- terminal embedding
- Git history/diff
- LSP availability and failure messaging
- mouse interactions including tab clicks, tree clicks, and drag-to-resize

### Release gates

- No uncaught exceptions during normal editor, terminal, Git, or LSP flows.
- Missing optional dependencies surface warnings and disabled features instead of crashes.
- One repo and multi-repo workspaces both work.

## Recommended implementation order for the first real build

1. Bootstrap package, config paths, command registry, and shell layout.
2. Add workspace persistence, multi-tab editing, dirty tracking, save flows.
3. Add focus management, dialogs, menu bar, command palette, and help overlay.
4. Land terminal embedding and panel toggling/resizing.
5. Land syntax coverage, quick open, and workspace search.
6. Land Git diff and file history tabs.
7. Land LSP definition and references.
8. Land AI fallback.
9. Land blame, line history, and final polish.

## Revisit Notes

When revisiting this plan later, check these questions first:

- Did Textual add native splitters or multi-root tree support?
- Is `textual-terminal` still the best PTY integration choice on Windows?
- Is `multilspy` still the best cross-platform LSP wrapper for Python and Scala?
- Has the desired AI integration changed from terminal-driving to direct API embedding?
- Should the project remain Python/Scala-focused, or expand language support sooner?
