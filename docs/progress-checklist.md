# tuide Progress Checklist

This checklist tracks implementation progress against `docs/implementation-plan.md`.

Status key:

- `done`: implemented enough for the current Linux-first milestone
- `partial`: implemented in a thin or provisional form
- `todo`: not implemented yet

## Phase 0: Bootstrap and feasibility spikes

- `done` project scaffold and package layout
- `done` Linux-first Textual app entrypoint
- `done` platform/config/workspace path helpers
- `partial` dependency capability detection
- `todo` explicit spike notes for splitters, multi-root tree, diff rendering, Windows PTY, Scala highlighting

## Phase 1: Editor shell MVP

- `done` 3-panel shell layout
- `partial` panel resizing
  Keyboard-based width adjustment exists; drag-to-resize does not.
- `done` focus cycling and basic `Esc` behavior
- `done` tabbed file opening from workspace tree
- `done` editable buffers
- `done` dirty tracking
- `done` save active file
- `done` close active tab
- `done` quit with unsaved-changes prompt
- `done` first-pass status bar

## Phase 2: Unified command system and interaction framework

- `partial` central command routing
  Command palette and top-bar actions route into app actions, but there is not yet a full formal command registry abstraction.
- `done` confirmation dialog
- `done` prompt dialog
- `done` help overlay
- `partial` menu bar
  Implemented as a clickable command bar, not full dropdown menus.
- `done` command palette
- `partial` reusable context action system
  Keyboard-driven context actions exist, but not full right-click mouse menus yet.

## Phase 3: Editing experience and content views

- `partial` language detection
  Basic extension mapping exists; full target-language highlighting strategy is incomplete.
- `partial` in-file find
  Opens a search results tab rather than a true inline find bar.
- `partial` quick open
  Uses a prompt plus picker flow, but not a native fuzzy finder yet.
- `partial` workspace-wide search
  Opens plain text result tabs from a prompt-based search.
- `partial` virtual tabs
  Read-only result/diff/history/blame tabs exist in a basic form.
- `todo` full syntax strategy for Scala and CSV/TSV

## Phase 4: Embedded terminal integration

- `partial` terminal panel
  `textual-terminal` integration path exists with fallback behavior.
- `done` shell selection
- `done` restart terminal action
- `partial` terminal capability reporting
- `todo` context menu in terminal
- `todo` verify resize behavior against real PTY widget

## Phase 5: Git inspection features

- `done` repo root detection
- `partial` diff with branch
  Opens a side-by-side read-only diff tab, but without synchronized scrolling or line-aware highlighting.
- `partial` file history
  Uses a commit picker and opens a side-by-side diff tab for the selected commit.
- `partial` blame
  Opens blame output in a tab, not as an editor gutter overlay.
- `partial` line history
  Line-range history can be opened in a read-only tab via a prompt, but it is not integrated with editor selections yet.
- `done` branch picker dialog

## Phase 6: LSP integration

- `partial` LSP capability detection
- `todo` actual multilspy integration
- `todo` per-repo server lifecycle
- `todo` real go-to-definition
- `todo` real find-references
- `todo` reference results list driven by LSP responses

## Phase 7: AI fallback and workflow integration

- `partial` AI fallback request generation
  The app prepares fallback prompts/results when LSP is unavailable.
- `todo` automatic prompt injection into the embedded terminal
- `todo` real AI session coordination
- `todo` status model that distinguishes live LSP vs live AI execution per request

## Phase 8: Final polish and hardening

- `partial` config persistence for panel sizes and default workspace
- `todo` theme and keybinding override persistence
- `todo` clickable status bar actions
- `todo` cross-platform docs beyond Linux-first testing
- `todo` contributor architecture guide
- `todo` comprehensive test matrix and release gates

## Immediate next priorities

1. Stabilize the Linux smoke-test path and fix any runtime issues found on a real Linux machine.
2. Replace the simplified workspace root handling with a true multi-root workspace explorer.
3. Upgrade Git views from plain text tabs to richer diff/history UI.
4. Implement real LSP request flow before deepening AI fallback behavior.
5. Add mouse drag splitters and stronger interaction polish.

## Git authentication — todo

- `todo` UI to configure git credentials (access token, username/password) stored in `~/.config/tuide/git-credentials.toml`
- `todo` inject configured credentials via `GIT_ASKPASS` helper script or `credential.helper` override when running push/pull/fetch
- `todo` support personal access token (PAT) flow for GitHub/GitLab/Bitbucket HTTPS remotes
- `todo` test push/pull against a private HTTPS remote with a stored PAT
- `todo` test push/pull against a private HTTPS remote with username + password
- `todo` test that a missing/wrong credential fails fast with a clear error (no freeze)
