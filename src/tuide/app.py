"""Main Textual application shell."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DirectoryTree, Footer, Header, Select, Static, TabbedContent, TextArea

from tuide.models import CapabilityStatus, ChoiceItem, CommandItem
from tuide.models import AppConfig
from tuide.services.config import ConfigStore
from tuide.services.git import GitService
from tuide.services.lsp import LspService
from tuide.services.search import SearchService
from tuide.platform import PlatformInfo, detect_platform
from tuide.services.workspace import WorkspaceStore
from tuide.widgets.dialogs import (
    CommandPaletteDialog,
    ConfirmDialog,
    HelpDialog,
    OptionPickerDialog,
    PromptDialog,
)
from tuide.widgets.editor import EditorPanel
from tuide.widgets.menubar import MenuBar
from tuide.widgets.panels import WorkspacePanel
from tuide.widgets.terminal import TerminalPanel, terminal_backend_available


class TuideApp(App[None]):
    """Linux-first shell for the tuide IDE."""

    CSS = """
    Screen {
        layout: vertical;
        background: #0b0f13;
        color: #eef2f5;
    }

    #root {
        height: 1fr;
        padding: 0 1 1 1;
    }

    .menu-bar {
        height: auto;
        padding: 1 0 1 0;
        background: transparent;
        dock: top;
    }

    .menu-group-label {
        color: #7f95aa;
        text-style: bold;
        margin: 0 1 0 0;
        padding: 1 0 0 0;
    }

    .menu-button {
        margin-right: 1;
        min-width: 10;
        background: #111a22;
        border: tall #223240;
        color: #dce7ef;
    }

    .menu-button:hover {
        background: #16222c;
    }

    .menu-button.-active,
    .menu-button:focus {
        border: tall #d8a548;
        color: #fff6dd;
    }

    #main-layout {
        height: 1fr;
        padding-top: 1;
    }

    .panel-frame {
        border: round #243748;
        background: #10171e;
        padding: 0 1 1 1;
        min-width: 24;
    }

    .panel-frame:focus-within {
        border: round #d8a548;
        background: #121c24;
    }

    #workspace-panel {
        width: 30;
    }

    #editor-panel {
        width: 1fr;
        margin: 0 1;
    }

    #terminal-panel {
        width: 34;
    }

    .panel-title {
        text-style: bold;
        color: #f2c66a;
        padding-top: 1;
        padding-bottom: 1;
    }

    .panel-body {
        padding: 1 0 1 0;
        color: #ced9e0;
    }

    .panel-subtitle {
        color: #8ea1b1;
        padding-bottom: 1;
    }

    .workspace-summary {
        background: #0d141b;
        border: round #1b2a37;
        color: #b8c7d3;
        height: auto;
        padding: 1;
        margin-bottom: 1;
    }

    #workspace-root-select {
        margin-bottom: 1;
    }

    #workspace-tree {
        height: 1fr;
        background: #0d141b;
        border: round #1b2a37;
        padding: 0 1;
    }

    #editor-tabs {
        height: 1fr;
        background: transparent;
        border-top: solid #1f2d38;
        padding-top: 1;
    }

    #editor-subtitle {
        color: #9ab0bf;
        padding-bottom: 1;
    }

    #welcome-copy,
    .editor-welcome {
        color: #ced9e0;
        padding: 2 1;
        background: #0d141b;
        border: round #1b2a37;
        width: 1fr;
    }

    .diff-view {
        height: 1fr;
    }

    .diff-pane {
        width: 1fr;
        padding: 0 1 1 0;
    }

    .terminal-fallback-copy {
        background: #0d141b;
        border: round #1b2a37;
        color: #ced9e0;
        padding: 2 1;
        margin-top: 1;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: #060a0d;
        color: #aab8c4;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "request_quit", "Quit"),
        Binding("escape", "escape_focus", "Dismiss", show=False),
        Binding("tab", "focus_next", "Next Focus", show=False),
        Binding("shift+tab", "focus_previous", "Prev Focus", show=False),
        Binding("ctrl+shift+p", "show_command_palette", "Palette"),
        Binding("ctrl+p", "quick_open", "Quick Open"),
        Binding("ctrl+s", "save_file", "Save"),
        Binding("ctrl+w", "close_tab", "Close Tab"),
        Binding("ctrl+f", "find_in_file", "Find"),
        Binding("ctrl+shift+f", "find_in_workspace", "Find in Workspace"),
        Binding("ctrl+.", "show_context_actions", "Context Actions"),
        Binding("ctrl+b", "toggle_workspace", "Toggle Workspace"),
        Binding("ctrl+j", "toggle_terminal", "Toggle Terminal"),
        Binding("ctrl+r", "restart_terminal", "Restart Terminal"),
        Binding("ctrl+alt+comma", "shrink_workspace", "Narrow Left", show=False),
        Binding("ctrl+alt+period", "grow_workspace", "Widen Left", show=False),
        Binding("ctrl+alt+bracketleft", "shrink_terminal", "Narrow Right", show=False),
        Binding("ctrl+alt+bracketright", "grow_terminal", "Widen Right", show=False),
        Binding("?", "show_help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.platform: PlatformInfo = detect_platform()
        self.config_store = ConfigStore()
        self.config = self.config_store.load()
        self.workspace_store = WorkspaceStore()
        self.workspace_state = self._load_workspace_state()
        self.git_service = GitService()
        self.lsp_service = LspService()
        self.search_service = SearchService()
        self.workspace_width = self.config.workspace_width
        self.terminal_width = self.config.terminal_width
        if self.platform.is_linux and terminal_backend_available():
            terminal_state = "ready"
        elif self.platform.is_linux:
            terminal_state = "install textual-terminal"
        else:
            terminal_state = "planned"
        self.capabilities = CapabilityStatus(
            terminal=terminal_state,
            git="ready" if self.git_service.is_available() else "missing-git",
            lsp=self.lsp_service.status_label(),
        )

    def compose(self) -> ComposeResult:
        """Compose the app shell."""
        yield Header(show_clock=False)
        with Vertical(id="root"):
            yield MenuBar()
            with Horizontal(id="main-layout"):
                yield WorkspacePanel(self.workspace_state)
                yield EditorPanel()
                yield TerminalPanel(self.platform.default_shell)
            yield Static(self.build_status_text(), id="status-bar")
        yield Footer()

    def _load_workspace_state(self):
        """Load workspace state and provide a cwd fallback for first launch."""
        workspace = self.workspace_store.load()
        if workspace.roots:
            return workspace
        if self.config.default_workspace:
            default_root = Path(self.config.default_workspace).expanduser()
            if default_root.exists():
                return type(workspace)(roots=[default_root])
        return type(workspace)(roots=[Path.cwd()])

    def build_status_text(self) -> str:
        """Return the first-pass status bar content."""
        root_count = len(self.workspace_state.roots)
        root_text = f"{root_count} workspace root{'s' if root_count != 1 else ''}"
        editor_panel = None
        if self.is_mounted:
            try:
                editor_panel = self.query_one(EditorPanel)
            except Exception:
                editor_panel = None
        document = editor_panel.active_document if editor_panel is not None else None
        cursor = editor_panel.active_cursor() if editor_panel is not None else None
        file_text = document.path.name if document is not None else "no file"
        dirty_text = "edited" if document and document.dirty else "clean"
        cursor_text = f"ln {cursor[0]}, col {cursor[1]}" if cursor is not None else "ln -, col -"
        return (
            f"{file_text} | {cursor_text} | {dirty_text} | {root_text} | {self.platform.system.lower()} | "
            f"terminal {self.capabilities.terminal} | git {self.capabilities.git} | "
            f"lsp {self.capabilities.lsp}"
        )

    def on_mount(self) -> None:
        """Set initial focus and title."""
        self.title = "tuide"
        self.sub_title = "Terminal IDE shell"
        self.apply_panel_widths()
        self.query_one(EditorPanel).focus()
        self.refresh_status()

    def refresh_status(self) -> None:
        """Update the first-pass status bar."""
        status = self.query_one("#status-bar", Static)
        status.update(self.build_status_text())

    async def wait_for_screen_result(self, screen) -> object | None:
        """Push a screen and wait for its dismissal result without requiring a worker."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[object | None] = loop.create_future()

        def _resolve(result: object | None) -> None:
            if not future.done():
                future.set_result(result)

        self.push_screen(screen, callback=_resolve)
        return await future

    @on(DirectoryTree.FileSelected)
    async def open_selected_file(self, event: DirectoryTree.FileSelected) -> None:
        """Open a selected file from the workspace tree."""
        await self.query_one(EditorPanel).open_file(event.path)
        self.refresh_status()

    @on(Select.Changed)
    async def handle_root_switch(self, event: Select.Changed) -> None:
        """Switch the active workspace root."""
        if event.select.id != "workspace-root-select" or event.value is Select.BLANK:
            return

        selected = Path(str(event.value))
        reordered = [selected] + [root for root in self.workspace_state.roots if root != selected]
        self.workspace_state = type(self.workspace_state)(roots=reordered)
        panel = self.query_one(WorkspacePanel)
        panel.update_workspace_state(self.workspace_state)
        self.workspace_store.save(self.workspace_state)
        await self.query_one("#workspace-tree", DirectoryTree).reload()
        self.refresh_status()

    @on(Button.Pressed)
    async def handle_button_press(self, event: Button.Pressed) -> None:
        """Route menu-bar button clicks to actions."""
        button_id = event.button.id
        if button_id == "menu-add-root":
            await self.action_add_workspace_root()
        elif button_id == "menu-remove-root":
            await self.action_remove_workspace_root()
        elif button_id == "menu-quick-open":
            await self.action_quick_open()
        elif button_id == "menu-find-file":
            await self.action_find_in_file()
        elif button_id == "menu-find-workspace":
            await self.action_find_in_workspace()
        elif button_id == "menu-palette":
            await self.action_show_command_palette()
        elif button_id == "menu-git-diff":
            await self.action_git_diff()
        elif button_id == "menu-git-history":
            await self.action_git_history()
        elif button_id == "menu-git-blame":
            await self.action_git_blame()
        elif button_id == "menu-git-line-history":
            await self.action_git_line_history()
        elif button_id == "menu-code-def":
            await self.action_code_goto_definition()
        elif button_id == "menu-code-refs":
            await self.action_code_find_references()

    @on(TextArea.Changed)
    @on(TextArea.SelectionChanged)
    def sync_editor_status(self) -> None:
        """Refresh status when editor contents or cursor position changes."""
        self.refresh_status()

    @on(TabbedContent.TabActivated)
    def sync_tab_status(self) -> None:
        """Refresh status when the active editor tab changes."""
        self.refresh_status()

    def action_focus_next(self) -> None:
        """Cycle focus forward across main panels."""
        self.screen.focus_next()

    def action_focus_previous(self) -> None:
        """Cycle focus backward across main panels."""
        self.screen.focus_previous()

    def action_toggle_workspace(self) -> None:
        """Show or hide the workspace panel."""
        panel = self.query_one("#workspace-panel")
        panel.display = not panel.display
        self.refresh_status()

    def action_toggle_terminal(self) -> None:
        """Show or hide the terminal panel."""
        panel = self.query_one("#terminal-panel")
        panel.display = not panel.display
        self.refresh_status()

    def action_save_file(self) -> None:
        """Save the active file if one is open."""
        saved = self.query_one(EditorPanel).save_active_file()
        if saved is not None:
            self.notify(f"Saved {saved.name}")
        self.refresh_status()

    async def action_close_tab(self) -> None:
        """Close the active editor tab."""
        editor = self.query_one(EditorPanel)
        active_document = editor.active_document
        if active_document is None:
            return

        if active_document.dirty:
            confirmed = await self.wait_for_screen_result(
                ConfirmDialog(
                    "Unsaved changes",
                    f"{active_document.path.name} has unsaved changes. Close it anyway?",
                    confirm_label="Close Tab",
                )
            )
            if not confirmed:
                return

        closed = await editor.close_active_tab()
        if closed is not None:
            self.notify(f"Closed {closed.name}")
        self.refresh_status()

    async def action_request_quit(self) -> None:
        """Quit the app, prompting if there are unsaved changes."""
        editor = self.query_one(EditorPanel)
        dirty_count = editor.dirty_count
        if dirty_count:
            confirmed = await self.wait_for_screen_result(
                ConfirmDialog(
                    "Unsaved changes",
                    f"You have {dirty_count} unsaved file{'s' if dirty_count != 1 else ''}. Quit anyway?",
                    confirm_label="Quit",
                )
            )
            if not confirmed:
                return
        self.exit()

    def action_restart_terminal(self) -> None:
        """Restart the embedded terminal when available."""
        restarted = self.query_one(TerminalPanel).restart()
        if restarted:
            self.notify("Terminal restarted")
        else:
            self.notify("Embedded terminal unavailable", severity="warning")

    def action_escape_focus(self) -> None:
        """Return focus to the editor when no modal is active."""
        self.query_one(EditorPanel).focus()

    def action_show_help(self) -> None:
        """Show the keybinding help overlay."""
        self.push_screen(HelpDialog())

    def command_items(self) -> list[CommandItem]:
        """Return palette commands."""
        return [
            CommandItem("workspace.add_root", "Add workspace root", "Add a folder to the workspace"),
            CommandItem("workspace.remove_root", "Remove workspace root", "Remove the active workspace root"),
            CommandItem("search.quick_open", "Quick open", "Open a file by name across the workspace"),
            CommandItem("search.find_file", "Find in file", "Search inside the active file"),
            CommandItem("search.find_workspace", "Find in workspace", "Search text across workspace roots"),
            CommandItem("view.toggle_workspace", "Toggle workspace", "Show or hide the left panel"),
            CommandItem("view.toggle_terminal", "Toggle terminal", "Show or hide the right panel"),
            CommandItem("git.diff", "Git diff with branch", "Compare current file to another branch"),
            CommandItem("git.history", "Git file history", "Show history for the active file"),
            CommandItem("git.blame", "Git blame", "Show blame for the active file"),
            CommandItem("git.line_history", "Git line history", "Show history for a chosen line range"),
            CommandItem("code.definition", "Go to definition", "Run code-intelligence definition action"),
            CommandItem("code.references", "Find references", "Run code-intelligence references action"),
            CommandItem("terminal.restart", "Restart terminal", "Restart the embedded terminal session"),
        ]

    async def action_show_command_palette(self) -> None:
        """Show a searchable command palette."""
        command_id = await self.wait_for_screen_result(CommandPaletteDialog(self.command_items()))
        if command_id is None:
            return
        await self.run_command(command_id)

    async def action_show_context_actions(self) -> None:
        """Show context actions based on the currently focused panel."""
        focused = self.focused
        if focused is None:
            await self.action_show_command_palette()
            return

        focused_id = focused.id or ""

        if focused_id in {"workspace-panel", "workspace-tree", "workspace-root-select", "workspace-roots"}:
            items = [
                ChoiceItem("workspace.add_root", "Add workspace root"),
                ChoiceItem("workspace.remove_root", "Remove active workspace root"),
                ChoiceItem("search.quick_open", "Quick open file"),
                ChoiceItem("search.find_workspace", "Search workspace"),
            ]
            title = "Workspace actions"
        elif focused_id in {"terminal-panel", "embedded-terminal", "terminal-fallback"}:
            items = [
                ChoiceItem("terminal.restart", "Restart terminal"),
                ChoiceItem("view.toggle_terminal", "Hide terminal panel"),
            ]
            title = "Terminal actions"
        else:
            items = [
                ChoiceItem("file.save", "Save active file"),
                ChoiceItem("file.close", "Close active tab"),
                ChoiceItem("search.find_file", "Find in file"),
                ChoiceItem("git.diff", "Git diff with branch"),
                ChoiceItem("git.history", "Git file history"),
                ChoiceItem("git.blame", "Git blame"),
                ChoiceItem("git.line_history", "Git line history"),
                ChoiceItem("code.definition", "Go to definition"),
                ChoiceItem("code.references", "Find references"),
            ]
            title = "Editor actions"

        action_id = await self.wait_for_screen_result(
            OptionPickerDialog(title, items, placeholder="Filter actions")
        )
        if action_id is None:
            return
        if action_id == "file.save":
            self.action_save_file()
            return
        if action_id == "file.close":
            await self.action_close_tab()
            return
        await self.run_command(action_id)

    async def run_command(self, command_id: str) -> None:
        """Dispatch a command identifier."""
        mapping = {
            "workspace.add_root": self.action_add_workspace_root,
            "workspace.remove_root": self.action_remove_workspace_root,
            "search.quick_open": self.action_quick_open,
            "search.find_file": self.action_find_in_file,
            "search.find_workspace": self.action_find_in_workspace,
            "git.diff": self.action_git_diff,
            "git.history": self.action_git_history,
            "git.blame": self.action_git_blame,
            "git.line_history": self.action_git_line_history,
            "code.definition": self.action_code_goto_definition,
            "code.references": self.action_code_find_references,
            "terminal.restart": self._run_restart_terminal,
        }
        if command_id == "view.toggle_workspace":
            self.action_toggle_workspace()
            return
        if command_id == "view.toggle_terminal":
            self.action_toggle_terminal()
            return
        action = mapping.get(command_id)
        if action is not None:
            result = action()
            if hasattr(result, "__await__"):
                await result

    def _run_restart_terminal(self) -> None:
        self.action_restart_terminal()

    async def action_add_workspace_root(self) -> None:
        """Prompt for and add a workspace root."""
        value = await self.wait_for_screen_result(
            PromptDialog("Add workspace root", placeholder="/path/to/project")
        )
        if not value:
            return

        root = Path(value).expanduser()
        if not root.exists() or not root.is_dir():
            self.notify("Workspace root must be an existing directory", severity="error")
            return

        self.workspace_state = self.workspace_store.add_root(self.workspace_state, root)
        self.workspace_store.save(self.workspace_state)
        self.config.default_workspace = str(self.workspace_state.roots[0])
        self.config_store.save(self.config)
        panel = self.query_one(WorkspacePanel)
        panel.update_workspace_state(self.workspace_state)
        await self.query_one("#workspace-tree", DirectoryTree).reload()
        self.refresh_status()

    async def action_quick_open(self) -> None:
        """Prompt for a filename and open the first workspace match."""
        query = await self.wait_for_screen_result(
            PromptDialog("Quick open", placeholder="filename or partial name")
        )
        if not query:
            return

        matches = self.search_service.find_files(self.workspace_state.roots, query, limit=25)
        if not matches:
            self.notify("No matching files found", severity="warning")
            return

        selected = await self.wait_for_screen_result(
            OptionPickerDialog(
                "Quick open results",
                [
                    ChoiceItem(
                        id=str(path),
                        label=path.name,
                        description=str(path.parent),
                    )
                    for path in matches
                ],
                placeholder="Filter matching files",
            )
        )
        if not selected:
            return

        chosen_path = Path(selected)
        await self.query_one(EditorPanel).open_file(chosen_path)
        self.notify(f"Opened {chosen_path.name}")
        self.refresh_status()

    async def action_find_in_file(self) -> None:
        """Search for text in the active file and open a results tab."""
        query = await self.wait_for_screen_result(
            PromptDialog("Find in file", placeholder="search text")
        )
        if not query:
            return

        matches = self.query_one(EditorPanel).find_in_active_file(query)
        title = f"find:{query}"
        text = "\n".join(matches) if matches else "No matches in active file."
        await self.query_one(EditorPanel).open_result_tab(title, text)
        self.refresh_status()

    async def action_find_in_workspace(self) -> None:
        """Search for text across workspace roots."""
        query = await self.wait_for_screen_result(
            PromptDialog("Find in workspace", placeholder="search text")
        )
        if not query:
            return

        matches = self.search_service.search_workspace_text(self.workspace_state.roots, query)
        title = f"workspace-search:{query}"
        text = "\n".join(matches) if matches else "No workspace matches found."
        await self.query_one(EditorPanel).open_result_tab(title, text)
        self.refresh_status()

    async def action_remove_workspace_root(self) -> None:
        """Remove the current workspace root."""
        if len(self.workspace_state.roots) <= 1:
            self.notify("Keep at least one workspace root", severity="warning")
            return

        current = self.workspace_state.roots[0]
        confirmed = await self.wait_for_screen_result(
            ConfirmDialog(
                "Remove workspace root",
                f"Remove {current} from the workspace?",
                confirm_label="Remove",
            )
        )
        if not confirmed:
            return

        self.workspace_state = self.workspace_store.remove_root(self.workspace_state, current)
        self.workspace_store.save(self.workspace_state)
        self.config.default_workspace = str(self.workspace_state.roots[0])
        self.config_store.save(self.config)
        panel = self.query_one(WorkspacePanel)
        panel.update_workspace_state(self.workspace_state)
        await self.query_one("#workspace-tree", DirectoryTree).reload()
        self.refresh_status()

    def active_file_context(self) -> tuple[Path, Path] | None:
        """Return active file and repo root when available."""
        path = self.query_one(EditorPanel).active_path
        if path is None:
            self.notify("Open a file first", severity="warning")
            return None

        repo_root = self.git_service.repo_root_for(path)
        if repo_root is None:
            self.notify("Active file is not inside a Git repository", severity="warning")
            return None
        return path, repo_root

    async def action_git_diff(self) -> None:
        """Open a branch diff tab for the active file."""
        context = self.active_file_context()
        if context is None:
            return
        path, repo_root = context
        branches = self.git_service.list_branches(repo_root)
        if not branches:
            self.notify("No Git branches found", severity="warning")
            return
        branch = await self.wait_for_screen_result(
            OptionPickerDialog(
                "Diff with branch",
                [ChoiceItem(id=name, label=name) for name in branches],
                placeholder="Filter branches",
            )
        )
        if not branch:
            return

        other = self.git_service.show_file(repo_root, branch, path)
        if other is None:
            self.notify("Unable to read file from that branch", severity="error")
            return
        current = path.read_text(encoding="utf-8", errors="replace")
        await self.query_one(EditorPanel).open_diff_tab(
            f"diff:{path.name}:{branch}",
            f"{branch}:{path.name}",
            other,
            str(path.name),
            current,
        )
        self.refresh_status()

    async def action_git_history(self) -> None:
        """Open file history for the active file."""
        context = self.active_file_context()
        if context is None:
            return
        path, repo_root = context
        history_entries = self.git_service.file_history_entries(repo_root, path)
        if not history_entries:
            self.notify("Unable to load file history", severity="error")
            return
        choice = await self.wait_for_screen_result(
            OptionPickerDialog(
                f"History for {path.name}",
                [
                    ChoiceItem(
                        id=entry.commit,
                        label=f"{entry.commit} {entry.subject}",
                        description=f"{entry.date} | {entry.author}",
                    )
                    for entry in history_entries
                ],
                placeholder="Filter commits",
            )
        )
        if not choice:
            return

        current_version = self.git_service.show_file(repo_root, choice, path)
        previous_version = self.git_service.show_file_parent(repo_root, choice, path)
        if current_version is None:
            self.notify("Unable to load selected commit", severity="error")
            return
        await self.query_one(EditorPanel).open_diff_tab(
            f"history-diff:{path.name}:{choice}",
            f"{choice}~1:{path.name}",
            previous_version or "",
            f"{choice}:{path.name}",
            current_version,
        )

    async def action_git_blame(self) -> None:
        """Open blame output for the active file."""
        context = self.active_file_context()
        if context is None:
            return
        path, repo_root = context
        blame = self.git_service.blame(repo_root, path)
        if blame is None:
            self.notify("Unable to load blame output", severity="error")
            return
        await self.query_one(EditorPanel).open_readonly_tab(f"blame:{path.name}", blame)

    async def action_git_line_history(self) -> None:
        """Open line history for a chosen line range."""
        context = self.active_file_context()
        if context is None:
            return
        path, repo_root = context
        value = await self.wait_for_screen_result(
            PromptDialog("Line history", placeholder="start:end, e.g. 10:20")
        )
        if not value:
            return
        try:
            start_raw, end_raw = value.split(":", 1)
            start_line = int(start_raw.strip())
            end_line = int(end_raw.strip())
        except ValueError:
            self.notify("Enter the range as start:end", severity="error")
            return
        if start_line <= 0 or end_line < start_line:
            self.notify("Line range must be positive and ordered", severity="error")
            return

        history = self.git_service.line_history(repo_root, path, start_line, end_line)
        if history is None:
            self.notify("Unable to load line history", severity="error")
            return
        await self.query_one(EditorPanel).open_readonly_tab(
            f"line-history:{path.name}:{start_line}-{end_line}",
            history,
        )

    async def action_code_goto_definition(self) -> None:
        """Perform the current definition action with LSP/AI fallback."""
        await self._run_code_intelligence("definition")

    async def action_code_find_references(self) -> None:
        """Perform the current references action with LSP/AI fallback."""
        await self._run_code_intelligence("references")

    async def _run_code_intelligence(self, intent: str) -> None:
        """Run code intelligence or AI fallback."""
        path = self.query_one(EditorPanel).active_path
        if path is None:
            self.notify("Open a file first", severity="warning")
            return

        symbol = await self.wait_for_screen_result(
            PromptDialog(f"{intent.title()} symbol", placeholder="symbol name")
        )
        if not symbol:
            return

        if self.lsp_service.available_for(path):
            server = self.lsp_service.language_server_for(path)
            text = (
                f"LSP server detected for {path.name}: {server}\n\n"
                f"Requested action: {intent}\n"
                f"Requested symbol: {symbol}\n\n"
                "Server lifecycle detection is in place, but request execution is still a scaffold."
            )
            await self.query_one(EditorPanel).open_result_tab(f"lsp:{intent}:{symbol}", text)
            return

        prompt = (
            f"AI fallback request\n\n"
            f"Action: {intent}\n"
            f"Symbol: {symbol}\n"
            f"File: {path}\n"
            f"Workspace root: {self.workspace_state.roots[0]}\n\n"
            f"Suggested terminal prompt:\n"
            f"Find the {intent} for '{symbol}' in this repo and explain where it lives."
        )
        await self.query_one(EditorPanel).open_result_tab(f"ai:{intent}:{symbol}", prompt)
        terminal = self.query_one("#terminal-panel")
        terminal.focus()
        self.notify("LSP unavailable, prepared AI fallback request", severity="warning")

    def apply_panel_widths(self) -> None:
        """Apply current panel widths."""
        self.query_one("#workspace-panel").styles.width = self.workspace_width
        self.query_one("#terminal-panel").styles.width = self.terminal_width
        self.config.workspace_width = self.workspace_width
        self.config.terminal_width = self.terminal_width
        self.config.default_workspace = str(self.workspace_state.roots[0])
        self.config_store.save(self.config)

    def action_shrink_workspace(self) -> None:
        self.workspace_width = max(20, self.workspace_width - 2)
        self.apply_panel_widths()

    def action_grow_workspace(self) -> None:
        self.workspace_width = min(60, self.workspace_width + 2)
        self.apply_panel_widths()

    def action_shrink_terminal(self) -> None:
        self.terminal_width = max(24, self.terminal_width - 2)
        self.apply_panel_widths()

    def action_grow_terminal(self) -> None:
        self.terminal_width = min(60, self.terminal_width + 2)
        self.apply_panel_widths()
