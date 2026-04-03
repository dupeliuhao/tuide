# tuide

`tuide` is a Linux-first terminal IDE scaffold built with Python and Textual.

## What it does today

The current build is a Linux-first shell with these working or first-pass features:

- left-panel file tree rooted at the current workspace
- multi-root workspace state with root add/remove prompts and active-root switching
- center tabbed editor that opens files from the tree
- editable `TextArea` buffers
- dirty-state tracking
- save with `Ctrl+S`
- close active tab with `Ctrl+W`
- unsaved-change confirmation on tab close and app quit
- top command/menu bar with clickable actions
- searchable command palette with `Ctrl+Shift+P`
- focus-aware context actions with `Ctrl+.`
- quick open file chooser with `Ctrl+P`
- in-file search with `Ctrl+F`
- workspace-wide search with `Ctrl+Shift+F`
- keybinding help overlay with `?`
- right-panel embedded terminal intended to run a real shell session
- keyboard-based panel resizing
- Git file diff/history/blame tabs for the active file
- Git line-history tab for an entered line range
- LSP availability detection for Python and Scala
- AI fallback request generation when LSP is unavailable

The long-term roadmap is in [docs/implementation-plan.md](D:\Github\tuide\docs\implementation-plan.md).

## Current project phase

`tuide` is currently in:

- Phase 1: editor shell MVP
- partial Phase 2: dialogs, menu, palette, and interaction polish
- partial Phase 4: Linux-first embedded terminal path
- early slices of Git and code-intelligence workflows

What is not implemented yet:

- mouse drag-to-resize splitters
- full dropdown menus
- true LSP request execution
- embedded AI transport into the terminal session
- synchronized/polished side-by-side diff behavior
- inline blame gutter rendering

## Linux install and test

Use these steps on your Linux machine:

Python requirement:

- Python 3.11 or newer

Check it with:

```bash
python3 --version
```

### 1. Clone or update the repo

```bash
git clone <your-repo-url> tuide
cd tuide
```

If you already have the repo:

```bash
cd tuide
git pull
```

### 2. Create a virtual environment

```bash
python3 -m venv vtuide
source vtuide/bin/activate
```

### 3. Install the app

```bash
python -m pip install --upgrade pip
pip install -e .[linux]
```

`tuide` currently expects a Textual version that stays compatible with `textual-terminal`.
The project now pins `textual` to a compatible range in `pyproject.toml`, so a fresh install
should give you a real embedded shell on Linux.
The project also now installs `textual[syntax]`, which is required for `TextArea` syntax
highlighting. If Python files still look plain after pulling, refresh the environment so the
syntax extras are installed.

If `textual-terminal` fails to install for any reason, you can still test the app shell without the embedded terminal:

```bash
pip install -e .
```

If you installed the project before this pin was added, refresh the environment with:

```bash
pip install --upgrade --force-reinstall -e .[linux]
```

If highlighting still does not appear, run this once inside the activated environment:

```bash
pip install --upgrade --force-reinstall "textual[syntax]>=0.58.0,<0.59.0"
```

If `textual-terminal` still ends up incompatible with your local environment, `tuide` will fall back to a placeholder instead of crashing on startup.

### 4. Launch the app

Run from the repo root so the workspace tree starts there by default:

```bash
tuide
```

If the entrypoint is not available for some reason, use:

```bash
python -m tuide.main
```

## First smoke test checklist

Once the app is open, try this:

1. Confirm the left panel shows the repo files.
2. Select a file in the tree and confirm it opens in the center tab area.
3. Edit the file and confirm the tab title gains a `*`.
4. Press `Ctrl+S` and confirm the dirty marker clears.
5. Edit again, then press `Ctrl+W` and confirm the unsaved-change dialog appears.
6. Press `?` and confirm the help overlay appears.
7. Press `Esc` and confirm focus returns toward the editor.
8. Press `Ctrl+Shift+P` and confirm the command palette opens and filters commands.
9. Press `Ctrl+P`, search for a filename, and choose a match from the picker.
10. Press `Ctrl+.` in different panels and confirm context-specific actions appear.
11. Press `Ctrl+F` and confirm active-file results open in a tab.
12. Press `Ctrl+Shift+F` and confirm workspace-wide matches open in a tab.
13. Add a second workspace root and switch between roots from the left panel selector.
14. Try `Diff`, `History`, `Blame`, or `Line Hist` from the top bar on a file inside a Git repo.
15. Press `?` or use the top bar code actions to exercise the LSP and AI fallback plumbing.
16. Confirm the right panel starts a real shell session.
17. Run a simple command such as `ls`.
18. Try launching an external CLI such as `kiro-cli` if it is installed.
19. Press `Ctrl+R` and confirm the terminal restarts.
20. Press `Ctrl+Q` with a dirty file and confirm the quit warning appears.

## Keybindings right now

- `Tab` / `Shift+Tab`: cycle focus
- `Ctrl+S`: save active file
- `Ctrl+W`: close active tab
- `Ctrl+Q`: quit with unsaved-change protection
- `Ctrl+P`: quick open
- `Ctrl+.`: context actions
- `Ctrl+F`: find in active file
- `Ctrl+Shift+F`: search in workspace
- `Ctrl+B`: toggle workspace panel
- `Ctrl+J`: toggle terminal panel
- `Ctrl+R`: restart terminal
- `Ctrl+Shift+P`: command palette
- `Ctrl+Alt+,` / `Ctrl+Alt+.`: resize workspace panel
- `Ctrl+Alt+[` / `Ctrl+Alt+]`: resize terminal panel
- `?`: show help
- `Esc`: return focus to the editor

## Notes

- The app is currently Linux-first by design.
- Windows and macOS abstraction seams are already present, but those targets are not the active testing focus yet.
- The right panel is meant to be a normal terminal, not a dedicated AI-only surface.
- If `git`, LSP servers, or terminal dependencies are missing, those advanced features are expected to be absent for now.
testing testing
testing 2 testing 2

test again
test 4
test 5