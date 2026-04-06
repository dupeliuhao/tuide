# tuide

`tuide` is a Linux-first lightweight terminal IDE for Git, diff, workspace search, and AI-assisted local workflows.

`v1.0.1` is the first release line that feels product-shaped rather than scaffold-shaped: multi-workspace support, polished Git flows, in-IDE conflict resolution, lightweight global search, and a cleaner interaction model built for users who already live in the terminal.

## What tuide is for

`tuide` is intentionally not trying to be a heavy IDE.

It is built for a workflow where:

- coding and refactors often happen through AI CLI tools or the terminal
- you still want a fast visual shell for diffs, file browsing, Git actions, and conflict resolution
- you want a local app that stays light and predictable

The design center is:

- fast file browsing
- lightweight editing with immediate local write-through
- Git-first workflows
- strong diff visibility
- minimal UI layers

## Highlights in v1.0.1

- multi-workspace file tree with add/remove workspace roots
- lightweight directory picker for adding roots
- file tree dirty markers on files and parent directories
- tabbed editor with persistent local changes
- quick open, file search, and global workspace search
- Git session menu with commit, push, fetch, update, merge, branch switch, and branch history
- push preview that shows unpushed commits, changed files, and diffs before push
- `Compare With Branch` and `Compare With Remote` for the active file
- in-IDE update and merge conflict resolution
- full-file three-pane conflict resolver with `Ours`, `Result`, and `Theirs`
- branch history and search flows that behave as layered single-tab workflows
- embedded terminal panel available on demand, but hidden by default
- one-line `curl | bash` installer
- automatic launcher installation into `~/.local/bin/tuide`

## Platform support

Right now `tuide` is actively targeted at Linux.

Expected environment:

- Linux
- Python `3.11+`
- a UTF-8 terminal

Git-heavy features work best if these tools are also installed:

- `git`
- `rg` (`ripgrep`)
- `fd` or `fdfind`
- `delta` for the best diff rendering

`tuide` can still run without every optional tool, but search and diff quality are better when they are present.

## Install

Fastest path:

```bash
curl -fsSL https://raw.githubusercontent.com/dupeliuhao/tuide/v1.0.1/scripts/install-remote.sh | bash
```

That path will:

- clone or update `tuide` into `~/.local/share/tuide`
- create the virtual environment
- install `tuide`
- install a launcher at `~/.local/bin/tuide`

If you prefer cloning first and installing locally:

```bash
git clone https://github.com/dupeliuhao/tuide.git
cd tuide
./install.sh
```

That local script will:

- install common Linux dependencies when possible
- create `vtuide`
- install `tuide`
- fall back automatically if the terminal extra cannot be installed

If you want the full manual path instead, use the steps below.

### 1. Clone the repo

```bash
git clone https://github.com/dupeliuhao/tuide.git
cd tuide
```

If you already have the repo:

```bash
git pull
```

### 2. Install Linux dependencies

Ubuntu / Debian:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip ripgrep fd-find
```

Optional but recommended:

```bash
sudo apt install -y git-delta
```

If your distro provides `fdfind` instead of `fd`, `tuide` can still use it once `fd` is available on `PATH`. If needed:

```bash
mkdir -p ~/.local/bin
ln -sf "$(command -v fdfind)" ~/.local/bin/fd
export PATH="$HOME/.local/bin:$PATH"
```

### 3. Create and activate a virtual environment

```bash
python3 -m venv vtuide
source vtuide/bin/activate
```

### 4. Install tuide

Recommended install:

```bash
python -m pip install --upgrade pip
pip install -e .[linux]
```

Fallback install if `textual-terminal` is unavailable in your environment:

```bash
pip install -e .
```

### 5. Launch

From the repo root:

```bash
tuide
```

Open a specific directory:

```bash
tuide /path/to/project
```

Check the installed version:

```bash
tuide --version
```

Fallback entrypoint:

```bash
python -m tuide.main
```

## Installer script options

The installer also supports a few useful flags:

```bash
./install.sh --help
./install.sh --skip-system-deps
./install.sh --no-terminal
./install.sh --venv-dir .venv
./install.sh --launcher-dir ~/.local/bin
./install.sh --no-launcher
```

## First-run checklist

For the smoothest first run:

1. Start inside a Git repo you actually want to work in.
2. Press `Ctrl+Shift+P` and confirm the command palette opens.
3. Press `Ctrl+P` and quick-open a file.
4. Edit a file and confirm the tab turns yellow and the file tree marks it dirty.
5. Open `Git` from the top bar and confirm your repo and branch are shown correctly.
6. Try `Commit`, then `Push Preview`.
7. Run `Global Search` with `Ctrl+Shift+F`.
8. If you want the embedded terminal, toggle it on with `Ctrl+J`.

## Core interaction model

`tuide` has a few important product rules:

- edits write through to local disk immediately
- “dirty” means different from Git `HEAD`, not “unsaved”
- `Esc` should unwind one UI layer at a time
- Git flows should stay inside `tuide` whenever possible
- terminal is secondary to Git/diff/editor workflows

This means:

- there is no separate save step
- `Ctrl+S` is intentionally gone
- commit/push/update/merge flows are the primary polished workflows

## Keybindings

- `Tab` / `Shift+Tab`: cycle focus
- `Ctrl+W`: close active tab
- `Ctrl+Q`: quit with confirmation
- `Ctrl+P`: quick open
- `Ctrl+.`: context actions
- `Ctrl+F`: find in active file
- `Ctrl+Shift+F`: global search
- `Ctrl+B`: toggle file tree
- `Ctrl+J`: toggle terminal panel
- `Ctrl+R`: restart terminal
- `Ctrl+Shift+P`: command palette
- `Ctrl+Alt+,` / `Ctrl+Alt+.`: resize workspace panel
- `Ctrl+Alt+[` / `Ctrl+Alt+]`: resize terminal panel
- `?`: show help
- `Esc`: go back one layer, or open quit confirmation from the main view

## Git features

Current Git flows are centered on a single active repo at a time:

- `Commit`
- `Push` with preview of unpushed commits
- `Fetch`
- `Update`
- `Merge Branch`
- `Branch History`
- compare current file with a branch or with upstream remote

In multi-workspace mode:

- `Global Search` is cross-workspace
- Git actions are single-repo and follow the active file when possible

## Conflict resolution

When `Update` or `Merge Branch` encounters conflicts, `tuide` keeps the workflow inside the app:

- choose merge or rebase when update diverges
- resolve conflicts in a three-pane full-file view
- left: `Ours`
- middle: `Result`
- right: `Theirs`

The goal is not to outgrow JetBrains or VS Code. The goal is to make Git-heavy AI-assisted terminal work less painful.

## Troubleshooting

### Search feels incomplete

Install `ripgrep` and `fd`, then reopen `tuide`.

### Embedded terminal looks different from your host terminal

`tuide` now tries to inherit the host terminal environment more closely, but the embedded panel is still a terminal widget inside a Textual app, not your raw host terminal.

### Diff rendering is less polished than `delta`

Install `git-delta`:

```bash
sudo apt install git-delta
```

`tuide` will also try to install `delta` automatically on startup if it is missing and the environment allows it.

### `textual-terminal` install fails

Use:

```bash
pip install -e .
```

`tuide` will still run without the embedded terminal backend.

## Release notes

See [CHANGELOG.md](CHANGELOG.md) for the `v1.0.1` release summary.
