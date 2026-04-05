"""Main Textual application shell."""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.text import Text as RichText
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, DirectoryTree, Input, Select, Static, TextArea

from tuide.models import CapabilityStatus, ChoiceItem, CommandItem
from tuide.services.config import ConfigStore
from tuide.services.git import GitService
from tuide.services.lsp import LspService
from tuide.services.python_navigation import PythonNavigationService, PythonNavigationTarget
from tuide.services.python_semantic import PythonSemanticService
from tuide.services.search import SearchService
from tuide.platform import PlatformInfo, detect_platform
from tuide.services.workspace import WorkspaceStore
from tuide.widgets.dialogs import (
    BranchPickerScreen,
    CommandPaletteDialog,
    ConfirmDialog,
    ContextMenuScreen,
    FindReferencesScreen,
    GlobalSearchDialog,
    GitCommitScreen,
    GitPushScreen,
    HelpDialog,
    OptionPickerDialog,
    PromptDialog,
)
from tuide.widgets.editor import EditorPanel, WrappingTabBar
from tuide.widgets.gitconflicts import GitConflictResolverScreen, GitConflictResolverView
from tuide.widgets.githistory import GitChangedFilesView, GitHistoryBrowserView, GitLogView
from tuide.widgets.menubar import MenuBar
from tuide.widgets.panels import WorkspacePanel
from tuide.widgets.splitter import VerticalSplitter
from tuide.widgets.terminal import TerminalPanel, terminal_backend_available


def _fmt_shortcut_key(key: str) -> str:
    """Convert a raw binding key string into a compact badge label."""
    result = (
        key.replace("ctrl+shift+", "^⇧")
           .replace("ctrl+alt+", "^⌥")
           .replace("ctrl+", "^")
           .replace("shift+", "⇧")
           .replace("alt+", "⌥")
    )
    if result and result[-1].isalpha():
        result = result[:-1] + result[-1].upper()
    return result


class ShortcutBar(Widget):
    """Bottom bar showing keybindings as [KEY] Description badge pairs.

    Each pair is clickable: clicking anywhere over a key or its description
    invokes the corresponding action.
    """

    can_focus = False

    DEFAULT_CSS = """
    ShortcutBar {
        dock: bottom;
        height: 1;
        background: #161b22;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        # List of (start_x, end_x, action_name) in content-relative coords.
        self._regions: list[tuple[int, int, str]] = []
        self._hovered: int | None = None  # index into _regions

    def render(self) -> RichText:
        text = RichText(no_wrap=True, overflow="ellipsis")
        self._regions = []
        x = 0
        text.append(" ")
        x += 1
        first = True
        for idx, binding in enumerate(b for b in self.app.BINDINGS if b.show):
            if not first:
                sep = "  │  "
                text.append(sep, style="#3d444d")
                x += len(sep)
            first = False
            hovered = self._hovered == idx
            key_style = "bold #fff7e6 on #8a5a16" if hovered else "bold #cae8ff on #1a3a6b"
            desc_style = "#fff1c2" if hovered else "#8b949e"
            start = x
            key_part = f" {_fmt_shortcut_key(binding.key)} "
            desc_part = f" {binding.description}"
            text.append(key_part, style=key_style)
            x += len(key_part)
            text.append(desc_part, style=desc_style)
            x += len(desc_part)
            self._regions.append((start, x, binding.action))
        return text

    def _region_at(self, mouse_x: int) -> int | None:
        for idx, (start, end, _) in enumerate(self._regions):
            if start <= mouse_x < end:
                return idx
        return None

    def on_mouse_move(self, event) -> None:
        new_hover = self._region_at(event.x)
        if new_hover != self._hovered:
            self._hovered = new_hover
            self.refresh()

    def on_leave(self, event) -> None:
        if self._hovered is not None:
            self._hovered = None
            self.refresh()

    def on_click(self, event) -> None:
        for start, end, action in self._regions:
            if start <= event.x < end:
                event.stop()
                self.run_worker(self.app.run_action(action), exclusive=False)
                return


class TuideApp(App[None]):
    """Linux-first shell for the tuide IDE."""

    NOTIFY_TIMEOUT = 3.0

    CSS = """
    Toast {
        width: auto;
        max-width: 55;
        padding: 0 1;
        height: auto;
    }

    ToastRack {
        padding: 0 1 1 0;
    }

    Screen {
        layout: vertical;
        background: #0d1117;
        color: #e6edf3;
    }

    #root {
        height: 1fr;
        padding: 0;
    }

    .menu-bar {
        height: auto;
        padding: 0;
        background: transparent;
        dock: top;
    }

    .menu-button {
        margin-right: 0;
        min-width: 2;
        min-height: 1;
        height: 1;
        padding: 0;
        background: #161b22;
        border: none;
        color: #c9d1d9;
    }

    .menu-button:hover {
        background: #2a2114;
    }

    .menu-button.-active,
    .menu-button:focus {
        background: #21262d;
        color: #e6edf3;
    }

    #main-layout {
        height: 1fr;
        padding-top: 0;
        background: #0d1117;
    }

    .panel-frame {
        border: none;
        background: #0d1117;
        padding: 0 0 0 0;
        min-width: 24;
    }

    .panel-frame:focus-within {
        background: #161b22;
    }

    .panel-splitter {
        width: 1;
        min-width: 1;
        height: 1fr;
        background: #3d444d;
        color: #3d444d;
    }

    .panel-splitter:hover,
    .panel-splitter.-dragging {
        background: #c9972b;
        color: #0d1117;
    }

    #workspace-panel {
        width: 30;
    }

    #editor-panel {
        width: 1fr;
        margin: 0;
    }

    #terminal-panel {
        width: 34;
    }

    #terminal-panel Terminal {
        background: #0d1117;
    }

    .panel-title {
        text-style: bold;
        color: #79c0ff;
        height: 1;
        padding: 0 1;
    }

    .panel-body {
        padding: 0;
        color: #c9d1d9;
    }

    .workspace-summary {
        background: #0d1117;
        border: solid #21262d;
        color: #8b949e;
        height: auto;
        padding: 0 1;
        margin: 0;
        display: none;
    }

    #workspace-root-select {
        margin: 0;
        height: 3;
    }

    #workspace-tree {
        height: 1fr;
        background: #0d1117;
        border: none;
        padding: 0;
        margin: 0;
    }

    /* editor-content handled above; terminal-tabs below */

    #terminal-tabs {
        height: 1fr;
        background: #0d1117;
        border-top: none;
        padding-top: 0;
        margin: 0;
    }

    /* TabbedContent internals (terminal panel) */
    #terminal-tabs ContentSwitcher {
        height: 1fr;
        background: #0d1117;
    }

    /* Git history widgets */
    GitLogView,
    GitChangedFilesView {
        height: 1fr;
        background: #0d1117;
        padding: 0;
    }

    .git-list-header {
        height: auto;
        padding: 0 1;
        background: #161b22;
        color: #8b949e;
    }

    GitLogView ListView,
    GitChangedFilesView ListView {
        background: #0d1117;
        height: 1fr;
        border: none;
        padding: 0;
    }

    GitLogView ListItem,
    GitChangedFilesView ListItem {
        background: #0d1117;
        height: auto;
        padding: 0 1;
    }

    GitLogView ListView.pointer-hover > ListItem.--highlight,
    GitChangedFilesView ListView.pointer-hover > ListItem.--highlight {
        background: #8a5a16;
    }

    GitLogView ListItem.--highlight,
    GitChangedFilesView ListItem.--highlight {
        background: #1f2d3d;
    }

    /* Transparent so the ListItem background (hover/highlight) shows through */
    GitLogView Static,
    GitChangedFilesView Static {
        background: transparent;
    }

    .commit-summary {
        height: 1;
        padding: 0;
        color: #e6edf3;
    }

    .commit-author {
        height: 1;
        padding: 0;
        color: #6e7681;
    }

    #editor-tab-bar {
        width: 1fr;
        height: auto;
        background: #0d1117;
        border-bottom: solid #21262d;
    }

    #editor-area {
        height: 1fr;
    }

    #editor-content {
        height: 1fr;
        background: #0d1117;
    }

    .editor-pane {
        height: 1fr;
        background: #0d1117;
    }

    TabPane {
        background: #0d1117;
        padding: 0;
    }

    /* Terminal still uses the built-in Tabs widget */
    #terminal-tabs > Tabs {
        background: #0d1117;
        border-bottom: none;
    }

    #terminal-tabs > Tabs #tabs-list,
    #terminal-tabs > Tabs #tabs-list-bar,
    #terminal-tabs > Tabs #tabs-scroll {
        background: #0d1117;
    }

    #terminal-tabs Tab {
        background: #0d1117;
        color: #8b949e;
        max-width: 28;
    }

    #terminal-tabs Tab.-active {
        background: #0d1117;
        color: #e6edf3;
    }

    #terminal-tabs Tab:hover {
        background: #161b22;
        color: #c9d1d9;
    }

    DirectoryTree {
        background: #0d1117;
    }

    Select {
        background: #0d1117;
    }

    SelectCurrent {
        background: #0d1117;
        border: none;
    }

    Tab.--dirty {
        color: #e8820c;
    }

    Tab.--dirty:hover {
        color: #f0a050;
    }

    Tab.--dirty.-active {
        color: #f0a050;
    }

    #welcome-copy,
    .editor-welcome {
        color: #8b949e;
        padding: 1 1;
        background: #0d1117;
        border: none;
        width: 1fr;
    }

    .diff-view {
        height: 1fr;
    }

    .diff-content {
        padding: 0;
        background: #0d1117;
    }

    .diff-pane {
        width: 1fr;
        padding: 0 1 1 0;
    }

    .terminal-add-btn {
        dock: right;
        width: 3;
        height: 3;
        min-width: 3;
        background: #0d1117;
        border: none;
        color: #8b949e;
    }

    .terminal-add-btn:hover {
        background: #2a2114;
        color: #f2cf86;
    }

    /* DirectoryTree colour consistency */
    DirectoryTree .directory-tree--file {
        color: #e6edf3;
    }

    DirectoryTree .directory-tree--folder {
        color: #79c0ff;
    }

    DirectoryTree .tree--cursor {
        background: #1f2d3d;
        color: #e6edf3;
    }

    DirectoryTree .tree--highlight {
        background: #21262d;
    }

    DirectoryTree .tree--guides {
        color: #3d444d;
    }

    .terminal-fallback-copy {
        background: #0d1117;
        border: none;
        color: #8b949e;
        padding: 1 1;
        margin: 0;
        height: 1fr;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: #010409;
        color: #8b949e;
        padding: 0;
    }

    #status-left {
        width: 1fr;
        padding: 0 1;
        height: 1;
    }

    #toggle-workspace-btn,
    #toggle-editor-btn,
    #toggle-terminal-btn {
        width: auto;
        height: 1;
        min-height: 1;
        padding: 0 1;
        border: none;
        background: #1f2d3d;
        color: #8b949e;
    }

    #toggle-workspace-btn:hover,
    #toggle-editor-btn:hover,
    #toggle-terminal-btn:hover {
        background: #5a4016;
        color: #fff1c2;
    }

    #branch-indicator {
        width: auto;
        height: 1;
        min-height: 1;
        padding: 0 1;
        border: none;
        background: #1f2d3d;
        color: #79c0ff;
    }

    #branch-indicator:hover {
        background: #5a4016;
        color: #fff7e6;
    }

    OptionList > .option-list--option-hover {
        background: #2a2114;
        color: #fff1c2;
    }

    OptionList > .option-list--option-hover-highlighted {
        background: #8a5a16;
        color: #fff7e6;
        text-style: bold;
    }

    .dismiss-button {
        background: #21262d;
        color: #ffffff;
        border: none;
    }

    .dismiss-button:hover {
        background: #8a5a16;
        color: #fff7e6;
    }

    .dismiss-button:focus {
        background: #21262d;
        color: #ffffff;
    }

    .dismiss-button.-active {
        background: #21262d;
        color: #ffffff;
    }

    .danger-button {
        background: #7a1f1f;
        color: #fff7f7;
        border: none;
    }

    .danger-button:hover,
    .danger-button:focus,
    .danger-button.-active {
        background: #b42323;
        color: #ffffff;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "request_quit", "Quit"),
        Binding("escape", "escape_focus", "Dismiss", show=False),
        Binding("tab", "focus_next", "Next Focus", show=False),
        Binding("shift+tab", "focus_previous", "Prev Focus", show=False),
        Binding("ctrl+shift+p", "show_command_palette", "Palette", show=False),
        Binding("ctrl+p", "quick_open", "Quick Open", show=False),
        Binding("ctrl+z", "undo_in_editor", "Undo", show=False),
        Binding("ctrl+shift+z", "redo_in_editor", "Redo", show=False),
        Binding("ctrl+w", "close_tab", "Close Tab", show=False, priority=True),
        Binding("ctrl+f", "find_in_file", "Find", priority=True),
        Binding("ctrl+shift+f", "find_in_workspace", "Global Search", priority=True),
        Binding("ctrl+.", "show_context_actions", "Context Actions", priority=True),
        Binding("ctrl+b", "toggle_workspace", "Toggle Workspace", priority=True),
        Binding("ctrl+e", "toggle_editor", "Toggle Editor", priority=True),
        Binding("ctrl+j", "toggle_terminal", "Toggle Terminal", priority=True),
        Binding("ctrl+r", "restart_terminal", "Restart Terminal", priority=True),
        Binding("ctrl+t", "new_terminal_tab", "New Terminal Tab", show=False, priority=True),
        Binding("ctrl+shift+w", "close_terminal_tab", "Close Terminal Tab", show=False, priority=True),
        Binding("ctrl+shift+g", "git_branch_history", "Git Log", show=False),
        Binding("ctrl+alt+comma", "shrink_workspace", "Narrow Left", show=False),
        Binding("ctrl+alt+period", "grow_workspace", "Widen Left", show=False),
        Binding("ctrl+alt+bracketleft", "shrink_terminal", "Narrow Right", show=False),
        Binding("ctrl+alt+bracketright", "grow_terminal", "Widen Right", show=False),
        Binding("?", "show_help", "Help"),
        Binding("ctrl+backslash", "editor_context_menu", "Context Menu", show=False),
    ]

    def __init__(self, startup_path: Path | None = None) -> None:
        super().__init__()
        self.platform: PlatformInfo = detect_platform()
        self.config_store = ConfigStore()
        self.config = self.config_store.load()
        self.workspace_store = WorkspaceStore()
        self._startup_path = startup_path
        self.workspace_state = self._load_workspace_state()
        self.git_service = GitService()
        self.lsp_service = LspService()
        self.python_navigation = PythonNavigationService()
        self.python_semantic = PythonSemanticService()
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
        self._cached_branch: str = "—"
        self._workspace_hidden_for_git_log = False
        self._terminal_hidden_for_git_log = False

    def compose(self) -> ComposeResult:
        """Compose the app shell."""
        with Vertical(id="root"):
            yield MenuBar()
            with Horizontal(id="main-layout"):
                yield WorkspacePanel(self.workspace_state)
                yield VerticalSplitter(self.adjust_workspace_by, id="workspace-splitter")
                yield EditorPanel()
                yield VerticalSplitter(self.adjust_terminal_by, id="terminal-splitter")
                yield TerminalPanel(self.platform.default_shell)
            with Horizontal(id="status-bar"):
                yield Static(self.build_status_text(), id="status-left")
                yield Button("Files", id="toggle-workspace-btn")
                yield Button("Editor", id="toggle-editor-btn")
                yield Button("Terminal", id="toggle-terminal-btn")
                yield Button("⎇ —", id="branch-indicator")
        yield ShortcutBar()

    def _load_workspace_state(self):
        """Load workspace state and provide a cwd fallback for first launch."""
        if self._startup_path is not None and self._startup_path.is_dir():
            return type(self.workspace_store.load())(roots=[self._startup_path])
        workspace = self.workspace_store.load()
        if workspace.roots:
            return workspace
        if self.config.default_workspace:
            default_root = Path(self.config.default_workspace).expanduser()
            if default_root.exists():
                return type(workspace)(roots=[default_root])
        return type(workspace)(roots=[Path.cwd()])

    def build_status_text(self) -> str:
        """Return the status bar left content."""
        editor_panel = None
        if self.is_mounted:
            try:
                editor_panel = self.query_one(EditorPanel)
            except Exception:
                pass
        document = editor_panel.active_document if editor_panel is not None else None
        cursor = editor_panel.active_cursor() if editor_panel is not None else None
        file_text = document.path.name if document is not None else "no file"
        dirty_text = " ●" if document and document.dirty else ""
        cursor_text = f"ln {cursor[0]}, col {cursor[1]}" if cursor is not None else "ln -, col -"
        root_count = len(self.workspace_state.roots)
        root_text = f"{root_count} root{'s' if root_count != 1 else ''}"
        return f"{file_text}{dirty_text}  {cursor_text}  {root_text}"

    def on_mount(self) -> None:
        """Set initial focus and title."""
        self.title = "tuide"
        self.sub_title = "Terminal IDE shell"
        self.apply_panel_widths()
        self.query_one("#terminal-panel").display = False
        self.query_one(EditorPanel).focus()
        self.refresh_status()
        self.sync_splitter_visibility()
        self._refresh_branch_indicator()
        self._open_welcome_if_project()
        self.set_interval(5.0, self._refresh_dirty_tree)
        self.run_worker(self._resume_active_conflict_session(), exclusive=False)

    def _open_welcome_if_project(self) -> None:
        """Open a welcome tab showing the project README, if a workspace root exists."""
        if not self.workspace_state.roots:
            return
        root = self.workspace_state.roots[0]
        project_name = root.name
        readme_text: str | None = None
        for candidate in ("README.md", "readme.md", "README.rst", "README.txt", "README"):
            readme_path = root / candidate
            if readme_path.is_file():
                try:
                    readme_text = readme_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
                break
        editor = self.query_one(EditorPanel)
        self.run_worker(editor.open_welcome_tab(project_name, readme_text), exclusive=False)

    def refresh_status(self) -> None:
        """Update the status bar left text (no git subprocess)."""
        if not self.is_mounted:
            return
        try:
            self.query_one("#status-left", Static).update(self.build_status_text())
        except Exception:
            pass

    def _main_editor_panel(self) -> EditorPanel | None:
        """Return the main editor panel even when a modal screen is active."""
        try:
            return self.query_one(EditorPanel)
        except Exception:
            pass
        try:
            if self.screen_stack:
                return self.screen_stack[0].query_one(EditorPanel)
        except Exception:
            pass
        return None

    def _refresh_branch_indicator(self) -> None:
        """Kick off a background thread to update the branch indicator."""
        if not self.is_mounted:
            return
        self.run_worker(self._fetch_branch_async(), exclusive=True, group="branch-refresh")

    def _refresh_dirty_tree(self) -> None:
        """Periodically refresh dirty-file markers in the workspace tree."""
        if not self.is_mounted:
            return
        self.run_worker(self._fetch_dirty_paths_async(), exclusive=True, group="dirty-tree")

    async def _fetch_dirty_paths_async(self) -> None:
        """Fetch changed files from git and update the workspace tree markers."""
        import asyncio
        repo_root = await asyncio.to_thread(self._find_repo_root)
        if repo_root is None:
            return
        files: list[tuple[str, str]] = await asyncio.to_thread(
            self.git_service.status_porcelain, repo_root
        )
        dirty: set[str] = {str(repo_root / filepath) for _xy, filepath in files}
        try:
            self.query_one(WorkspacePanel).set_dirty_paths(dirty)
        except Exception:
            pass

    async def _fetch_branch_async(self) -> None:
        """Fetch current branch in a thread and update the indicator."""
        import asyncio
        repo_root = await asyncio.to_thread(self._find_repo_root)
        if repo_root is None:
            label = "⎇ —"
        else:
            branch = await asyncio.to_thread(self.git_service.current_branch, repo_root)
            label = f"⎇ {branch or 'detached'}"
        self._cached_branch = label.removeprefix("⎇ ")
        try:
            self.query_one("#branch-indicator", Button).label = label
        except Exception:
            pass

    async def action_open_branch_picker(self) -> None:
        """Open the branch picker popup."""
        repo_root = self._find_repo_root()
        if repo_root is None:
            self.notify("No git repository found", severity="warning")
            return
        branches = self.git_service.list_all_branches(repo_root)
        if not branches:
            self.notify("No branches found", severity="warning")
            return
        current = self.git_service.current_branch(repo_root) or "detached"
        selected = await self.wait_for_screen_result(BranchPickerScreen(branches, current))
        if not selected or selected == current:
            return
        success, output = self.git_service.checkout_branch(repo_root, selected)
        severity = "information" if success else "error"
        self.notify(f"{'→' if success else '✗'} {selected}" + ("" if success else f"\n{output}"), severity=severity)
        self._refresh_branch_indicator()

    def show_confirm_dialog(
        self,
        title: str,
        message: str,
        *,
        confirm_label: str,
        confirm_variant: str = "warning",
        confirm_classes: str = "",
        on_confirm,
    ) -> None:
        """Show a confirm dialog and run a callback only when confirmed."""

        def _resolve(result: object | None) -> None:
            if result:
                on_confirm()

        self._push_modal_screen(
            ConfirmDialog(
                title,
                message,
                confirm_label=confirm_label,
                confirm_variant=confirm_variant,
                confirm_classes=confirm_classes,
            ),
            callback=_resolve,
        )

    def _restore_focus_after_modal(self, previous_focus: Widget | None) -> None:
        """Return focus to the prior widget or a stable main-view fallback."""
        if len(self.screen_stack) > 1:
            return

        if (
            previous_focus is not None
            and previous_focus.is_mounted
            and previous_focus.screen is self.screen_stack[0]
        ):
            previous_focus.focus()
            return

        try:
            self.query_one(EditorPanel).focus()
        except Exception:
            self.focus()

    def _push_modal_screen(self, screen, callback=None) -> None:
        """Push a modal and restore main-view focus when it closes."""
        previous_focus = self.focused

        def _resolve(result: object | None) -> None:
            if callback is not None:
                callback(result)
            self.call_after_refresh(self._restore_focus_after_modal, previous_focus)

        self.push_screen(screen, callback=_resolve)

    async def wait_for_screen_result(self, screen) -> object | None:
        """Push a screen and wait for its dismissal result without requiring a worker."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[object | None] = loop.create_future()

        def _resolve(result: object | None) -> None:
            if not future.done():
                future.set_result(result)

        self._push_modal_screen(screen, callback=_resolve)
        return await future

    @on(GitCommitScreen.FileDiscarded)
    def _on_file_discarded(self, event: GitCommitScreen.FileDiscarded) -> None:
        """Reload the editor tab after a file is restored to HEAD via Discard."""
        try:
            editor = self.screen_stack[0].query_one(EditorPanel)
        except Exception:
            return
        editor.reload_file(event.path)
        self.refresh_status()
        self._refresh_dirty_tree()

    async def _open_editor_file(self, path: Path) -> None:
        """Open a file in the editor, supplying git HEAD text for dirty tracking."""
        repo_root = self.git_service.repo_root_for(path)
        git_head_text: str | None = None
        if repo_root is not None:
            git_head_text = self.git_service.show_file(repo_root, "HEAD", path)
        editor = self._main_editor_panel()
        if editor is None:
            raise NoMatches("Main EditorPanel is not mounted")
        await editor.open_file(path, git_head_text=git_head_text)
        self.refresh_status()

    @on(DirectoryTree.FileSelected)
    async def open_selected_file(self, event: DirectoryTree.FileSelected) -> None:
        """Open a selected file from the workspace tree."""
        await self._open_editor_file(event.path)

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
    def handle_button_press(self, event: Button.Pressed) -> None:
        """Route menu-bar button clicks to actions."""
        button_id = event.button.id
        if button_id is None:
            return

        if button_id == "toggle-editor-btn":
            self.action_toggle_editor()
            return
        if button_id == "toggle-workspace-btn":
            self.action_toggle_workspace()
            return
        if button_id == "toggle-terminal-btn":
            self.action_toggle_terminal()
            return
        if button_id == "branch-indicator":
            self.run_worker(self.action_open_branch_picker(), exclusive=False)
            return
        if button_id == "new-terminal-tab-btn":
            self.action_new_terminal_tab()
            return
        if not button_id.startswith("menu-"):
            return
        if button_id == "menu-add-root":
            self.run_worker(self.action_add_workspace_root(), exclusive=False)
        elif button_id == "menu-remove-root":
            self.run_worker(self.action_remove_workspace_root(), exclusive=False)
        elif button_id == "menu-git-session":
            self.run_worker(self.action_git_session(), exclusive=False)
        elif button_id == "menu-todo":
            self.run_worker(self.action_todo_list(), exclusive=False)
        elif button_id == "menu-quick-open":
            self.run_worker(self.action_quick_open(), exclusive=False)
        elif button_id == "menu-find-file":
            self.run_worker(self.action_find_in_file(), exclusive=False)
        elif button_id == "menu-find-workspace":
            self.run_worker(self.action_find_in_workspace(), exclusive=False)
        elif button_id == "menu-palette":
            self.run_worker(self.action_show_command_palette(), exclusive=False)
        elif button_id == "menu-git-diff":
            self.run_worker(self.action_git_diff(), exclusive=False)
        elif button_id == "menu-git-history":
            self.run_worker(self.action_git_history(), exclusive=False)
        elif button_id == "menu-git-blame":
            self.run_worker(self.action_git_blame(), exclusive=False)
        elif button_id == "menu-git-line-history":
            self.run_worker(self.action_git_line_history(), exclusive=False)
        elif button_id == "menu-code-def":
            self.run_worker(self.action_code_goto_definition(), exclusive=False)
        elif button_id == "menu-code-refs":
            self.run_worker(self.action_code_find_references(), exclusive=False)
        elif button_id == "menu-quit":
            self.run_worker(self.action_request_quit(), exclusive=False)

    @on(TextArea.Changed)
    @on(TextArea.SelectionChanged)
    def sync_editor_status(self) -> None:
        """Refresh status when editor contents or cursor position changes."""
        self.refresh_status()

    @on(WrappingTabBar.TabActivated)
    def sync_tab_status(self) -> None:
        """Refresh status and branch when the active editor tab changes."""
        self.refresh_status()
        self._refresh_branch_indicator()

    def on_mouse_up(self, event) -> None:
        """Handle mouse-up: × close on editor tabs, right-click context menus."""
        if event.button == 1:
            self._maybe_close_editor_tab(event.screen_x, event.screen_y)
            return
        if event.button not in (2, 3):
            return
        if len(self.screen_stack) > 1:
            return
        editor = self.query_one(EditorPanel)
        if not editor.region.contains(event.screen_x, event.screen_y):
            return

        # Right-click on the wrapping tab bar → tab context menu
        try:
            tab_bar = editor.query_one("WrappingTabBar")
            if tab_bar.region.contains(event.screen_x, event.screen_y):
                self.run_worker(
                    self._show_tab_context_menu(event.screen_x, event.screen_y),
                    exclusive=False,
                )
                return
        except Exception:
            pass

        # Right-click in editor content area
        if editor.active_text_area is None:
            return
        self.run_worker(
            self._show_editor_context_menu(event.screen_x, event.screen_y),
            exclusive=False,
        )

    async def action_editor_context_menu(self) -> None:
        """Open context menu at the centre of the editor (keyboard trigger)."""
        editor = self.query_one(EditorPanel)
        if editor.active_text_area is None:
            self.notify("Open a file first", severity="warning")
            return
        r = editor.region
        await self._show_editor_context_menu(r.x + r.width // 2, r.y + r.height // 2)

    def _maybe_close_editor_tab(self, sx: int, sy: int) -> None:
        """Close an editor or terminal tab when the × in its label is clicked."""
        # ContentTab IDs are prefixed with "--content-tab-"; strip it to get the pane id.
        _PREFIX = "--content-tab-"

        try:
            editor = self.query_one(EditorPanel)
        except Exception:
            return
        if editor.region.contains(sx, sy):
            # WrappingTabBar handles its own × clicks; nothing to do here.
            return
        try:
            terminal = self.query_one(TerminalPanel)
        except Exception:
            return
        if terminal.region.contains(sx, sy):
            try:
                tabs_bar = terminal.query_one("Tabs")
                if tabs_bar.region.contains(sx, sy):
                    for tab in tabs_bar.query("Tab"):
                        r = tab.region
                        if not r.contains(sx, sy):
                            continue
                        pane_id = tab.id.removeprefix(_PREFIX)
                        # × occupies the last 2 columns of the tab (right padding is 1)
                        if sx >= r.right - 2:
                            terminal._tabs.active = pane_id
                            self.run_worker(self._close_terminal_tab(), exclusive=False)
                        break
            except Exception:
                pass

    async def _show_tab_context_menu(self, x: int, y: int) -> None:
        """Show a right-click context menu for the editor tab bar."""
        items = [ChoiceItem("tab.close", "Close tab")]

        action_id = await self.wait_for_screen_result(ContextMenuScreen(items, x, y))
        if action_id == "tab.close":
            await self.action_close_tab()

    async def _show_editor_context_menu(self, x: int, y: int) -> None:
        """Build and show the right-click context menu for the editor."""
        editor = self.query_one(EditorPanel)
        ta = editor.active_text_area
        if ta is None:
            return

        selected = ta.selected_text.strip()
        short = (selected[:24] + "…") if len(selected) > 24 else selected

        items: list[ChoiceItem] = []
        if selected:
            items += [
                ChoiceItem("ctx.find_selected", f'Find: "{short}"'),
                ChoiceItem("ctx.find_workspace_selected", f'Find in workspace: "{short}"'),
                ChoiceItem("ctx.git_line_history", "Git history for selection"),
            ]

        items += [
            ChoiceItem("ctx.git_diff", "Compare With Branch"),
            ChoiceItem("ctx.git_diff_remote", "Compare With Remote"),
            ChoiceItem("ctx.git_history", "Git file history"),
            ChoiceItem("ctx.git_blame", "Git blame"),
            ChoiceItem("ctx.definition", "Go to definition"),
            ChoiceItem("ctx.references", "Find references"),
            ChoiceItem("ctx.python_outline", "Python outline"),
        ]

        action_id = await self.wait_for_screen_result(ContextMenuScreen(items, x, y))
        if action_id is None:
            return

        if action_id == "ctx.find_selected":
            matches = editor.find_in_active_file(selected)
            text = "\n".join(matches) if matches else "No matches."
            await editor.open_result_tab(f"find:{short}", text)
        elif action_id == "ctx.find_workspace_selected":
            await self._run_workspace_text_search(selected, title="Workspace Search")
        elif action_id == "ctx.git_line_history":
            cursor = editor.active_cursor()
            start, end = (cursor[0], cursor[0]) if cursor else (1, 1)
            context = self.active_file_context()
            if context:
                path, repo_root = context
                history = self.git_service.line_history(repo_root, path, start, end)
                if history:
                    await editor.open_readonly_tab(f"line-history:{path.name}:{start}-{end}", history)
                else:
                    self.notify("No line history found", severity="warning")
        elif action_id in {"ctx.git_diff", "ctx.git_diff_remote", "ctx.git_history", "ctx.git_blame",
                           "ctx.definition", "ctx.references", "ctx.python_outline"}:
            mapping = {
                "ctx.git_diff": "git.diff",
                "ctx.git_diff_remote": "git.diff_remote",
                "ctx.git_history": "git.history",
                "ctx.git_blame": "git.blame",
                "ctx.definition": "code.definition",
                "ctx.references": "code.references",
                "ctx.python_outline": "python.outline",
            }
            await self.run_command(mapping[action_id])

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
        self.sync_splitter_visibility()
        self.refresh_status()

    def action_toggle_editor(self) -> None:
        """Show or hide the editor panel."""
        panel = self.query_one("#editor-panel")
        panel.display = not panel.display
        terminal = self.query_one("#terminal-panel")
        if not panel.display:
            # Editor hidden — let terminal fill the freed space
            terminal.styles.width = "1fr"
        else:
            # Editor restored — return terminal to its saved width
            terminal.styles.width = self.terminal_width
        self.sync_splitter_visibility()
        terminal.refresh(layout=True)
        self.query_one("#main-layout").refresh(layout=True)
        self.refresh(layout=True)
        self.refresh_status()

    def action_toggle_terminal(self) -> None:
        """Show or hide the terminal panel."""
        panel = self.query_one("#terminal-panel")
        panel.display = not panel.display
        self.sync_splitter_visibility()
        self.refresh_status()

    def action_undo_in_editor(self) -> None:
        """Undo the last edit in the active editor."""
        editor = self.query_one(EditorPanel).active_text_area
        if editor is not None:
            editor.action_undo()

    def action_redo_in_editor(self) -> None:
        """Redo the last undone edit in the active editor."""
        editor = self.query_one(EditorPanel).active_text_area
        if editor is not None:
            editor.action_redo()

    async def action_close_tab(self) -> None:
        """Close the active editor tab."""
        editor = self.query_one(EditorPanel)
        active_document = editor.active_document

        if active_document is None:
            # Virtual or Welcome tab — delegate directly (no dirty check needed)
            await self._close_active_tab_after_confirm()
            return

        if active_document.dirty:
            self.show_confirm_dialog(
                "Unsaved changes",
                f"{active_document.path.name} has unsaved changes. Close it anyway?",
                confirm_label="Close Tab",
                on_confirm=lambda: self.run_worker(self._close_active_tab_after_confirm(), exclusive=False),
            )
            return

        await self._close_active_tab_after_confirm()

    async def _close_active_tab_after_confirm(self) -> None:
        """Close the active tab after confirmation has been resolved."""
        closed = await self.query_one(EditorPanel).close_active_tab()
        if closed is not None:
            self.notify(f"Closed {closed.name}")
        self.refresh_status()

    async def action_request_quit(self) -> None:
        """Quit the app only after an explicit confirmation."""
        editor = self.query_one(EditorPanel)
        dirty_count = editor.dirty_count
        if dirty_count:
            title = "Quit tuide?"
            message = (
                f"You have {dirty_count} local file change{'s' if dirty_count != 1 else ''} "
                "that are not committed. Quit anyway?"
            )
        else:
            title = "Quit tuide?"
            message = "Exit tuide and return to the terminal?"
        self.show_confirm_dialog(
            title,
            message,
            confirm_label="Quit",
            confirm_variant="error",
            confirm_classes="danger-button",
            on_confirm=lambda: self.call_after_refresh(self.exit),
        )

    def action_restart_terminal(self) -> None:
        """Restart the active terminal tab when available."""
        restarted = self.query_one(TerminalPanel).restart_active()
        if restarted:
            self.notify("Terminal restarted")
        else:
            self.notify("Embedded terminal unavailable", severity="warning")

    def action_new_terminal_tab(self) -> None:
        """Open a new terminal tab."""
        self.run_worker(self.query_one(TerminalPanel).new_tab(), exclusive=False)

    def action_close_terminal_tab(self) -> None:
        """Close the active terminal tab."""
        self.run_worker(self._close_terminal_tab(), exclusive=False)

    async def _close_terminal_tab(self) -> None:
        closed = await self.query_one(TerminalPanel).close_active_tab()
        if not closed:
            return

    @on(TerminalPanel.HideRequested)
    def _on_terminal_hide_requested(self) -> None:
        """Hide the terminal panel when its last tab is closed."""
        panel = self.query_one("#terminal-panel")
        if not panel.display:
            return
        panel.display = False
        self.sync_splitter_visibility()
        self.refresh_status()

    def action_escape_focus(self) -> None:
        """Unwind UI layers, or open quit confirmation from the main shell."""
        if len(self.screen_stack) > 1:
            top_screen = self.screen_stack[-1]
            handle_escape = getattr(top_screen, "handle_escape", None)
            if callable(handle_escape) and handle_escape():
                return
            top_screen.dismiss(None)
            return
        self.run_worker(self.action_request_quit(), exclusive=False)

    def action_show_help(self) -> None:
        """Show the keybinding help overlay."""
        self._push_modal_screen(HelpDialog())

    def command_items(self) -> list[CommandItem]:
        """Return palette commands."""
        return [
            CommandItem("workspace.add_root", "Add workspace root", "Add a folder to the workspace"),
            CommandItem("workspace.remove_root", "Remove workspace root", "Remove the active workspace root"),
            CommandItem("search.quick_open", "Quick open", "Open a file by name across the workspace"),
            CommandItem("search.find_file", "Find in file", "Search inside the active file"),
            CommandItem("search.find_workspace", "Global search", "Search text, files, and lightweight symbols across the workspace"),
            CommandItem("view.toggle_workspace", "Toggle workspace", "Show or hide the left panel"),
            CommandItem("view.toggle_terminal", "Toggle terminal", "Show or hide the right panel"),
            CommandItem("git.branch_history", "Git branch history", "Browse commits on the current branch"),
            CommandItem("git.session", "Git session", "Open project-level Git actions"),
            CommandItem("git.diff", "Compare With Branch", "Compare current file to another branch"),
            CommandItem("git.diff_remote", "Compare With Remote", "Compare current file to the current branch upstream"),
            CommandItem("git.changed_files", "Git changed files", "Show side-by-side diff for any file changed vs HEAD"),
            CommandItem("git.history", "Git file history", "Show history for the active file"),
            CommandItem("git.blame", "Git blame", "Show blame for the active file"),
            CommandItem("git.line_history", "Git line history", "Show history for a chosen line range"),
            CommandItem("todo.list", "Todo list", "Open TODO.md from the current workspace"),
            CommandItem("python.outline", "Python outline", "Show function, class, and usage summary for the active file"),
            CommandItem("python.symbol", "Python symbol details", "Show definitions and usages for the symbol at the cursor"),
            CommandItem("code.definition", "Go to definition", "Run code-intelligence definition action"),
            CommandItem("code.references", "Find references", "Run code-intelligence references action"),
            CommandItem("terminal.restart", "Restart terminal", "Restart the active terminal tab"),
            CommandItem("terminal.new_tab", "New terminal tab", "Open a new terminal tab"),
            CommandItem("terminal.close_tab", "Close terminal tab", "Close the active terminal tab"),
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
                ChoiceItem("todo.list", "Todo list"),
                ChoiceItem("search.quick_open", "Quick open file"),
                ChoiceItem("search.find_workspace", "Global search"),
            ]
            title = "Workspace actions"
        elif focused_id == "terminal-panel" or focused_id.startswith("embedded-terminal") or focused_id.startswith("terminal-fallback"):
            items = [
                ChoiceItem("terminal.new_tab", "New terminal tab"),
                ChoiceItem("terminal.close_tab", "Close terminal tab"),
                ChoiceItem("terminal.restart", "Restart terminal"),
                ChoiceItem("view.toggle_terminal", "Hide terminal panel"),
            ]
            title = "Terminal actions"
        else:
            items = [
                ChoiceItem("file.close", "Close active tab"),
                ChoiceItem("search.find_file", "Find in file"),
                ChoiceItem("git.diff", "Compare With Branch"),
                ChoiceItem("git.diff_remote", "Compare With Remote"),
                ChoiceItem("git.history", "Git file history"),
                ChoiceItem("git.blame", "Git blame"),
                ChoiceItem("git.line_history", "Git line history"),
                ChoiceItem("python.outline", "Python outline"),
                ChoiceItem("python.symbol", "Python symbol details"),
                ChoiceItem("code.definition", "Go to definition"),
                ChoiceItem("code.references", "Find references"),
            ]
            title = "Editor actions"

        action_id = await self.wait_for_screen_result(
            OptionPickerDialog(title, items, placeholder="Filter actions")
        )
        if action_id is None:
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
            "git.branch_history": self.action_git_branch_history,
            "git.session": self.action_git_session,
            "git.diff": self.action_git_diff,
            "git.diff_remote": self.action_git_diff_remote,
            "git.changed_files": self.action_git_changed_files,
            "git.history": self.action_git_history,
            "git.blame": self.action_git_blame,
            "git.line_history": self.action_git_line_history,
            "todo.list": self.action_todo_list,
            "python.outline": self.action_python_outline,
            "python.symbol": self.action_python_symbol_details,
            "code.definition": self.action_code_goto_definition,
            "code.references": self.action_code_find_references,
            "terminal.restart": self._run_restart_terminal,
            "terminal.new_tab": self.action_new_terminal_tab,
            "terminal.close_tab": self.action_close_terminal_tab,
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
        await self._open_editor_file(chosen_path)
        self.notify(f"Opened {chosen_path.name}")

    async def action_todo_list(self) -> None:
        """Open the TODO list (or create one in the first workspace root)."""
        roots = list(self.workspace_state.roots) or [Path.cwd()]
        todo_path: Path | None = None

        for root in roots:
            candidate = root / "TODO.md"
            if candidate.exists():
                todo_path = candidate
                break

        if todo_path is None:
            todo_path = roots[0] / "TODO.md"
            todo_path.write_text(
                "# TODO\n\n- [ ] Add tasks here\n",
                encoding="utf-8",
            )

        await self._open_editor_file(todo_path)

    async def action_find_in_file(self) -> None:
        """Open the inline find bar in the active editor."""
        self.query_one(EditorPanel).open_find_bar()

    async def action_find_in_workspace(self) -> None:
        """Run lightweight global search across workspace text or names."""
        request = await self.wait_for_screen_result(GlobalSearchDialog())
        if request is None:
            return
        mode, query, case_sensitive = request

        if mode == "search.workspace.names":
            await self._run_workspace_name_search(query, case_sensitive=case_sensitive)
            return

        await self._run_workspace_text_search(query, case_sensitive=case_sensitive)

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

    def _find_repo_root(self) -> Path | None:
        """Return the current Git repo root without side effects."""
        try:
            path = self.query_one(EditorPanel).active_path
        except Exception:
            path = None
        if path is not None:
            repo_root = self.git_service.repo_root_for(path)
            if repo_root is not None:
                return repo_root
        for root in self.workspace_state.roots:
            repo_root = self.git_service.repo_root_for(root)
            if repo_root is not None:
                return repo_root
        return None

    def active_repo_root(self) -> Path | None:
        """Return the current Git repository root, notifying on failure."""
        repo_root = self._find_repo_root()
        if repo_root is None:
            self.notify("No Git repository found in the current workspace", severity="warning")
        return repo_root

    async def open_git_output_tab(self, title: str, repo_root: Path, output: str) -> None:
        """Open Git command output in a result tab."""
        branch = self.git_service.current_branch(repo_root) or "detached"
        text = f"Repo: {repo_root}\nBranch: {branch}\n\n{output}"
        editor = self.screen_stack[0].query_one(EditorPanel)
        await editor.open_readonly_tab(title, text)
        self.refresh_status()

    async def _close_git_output_tabs(self, *titles: str) -> None:
        """Close transient Git result tabs when the command succeeded."""
        editor = self._main_editor_panel()
        if editor is None:
            return
        for title in titles:
            await editor.close_virtual_tab(title)

    def _git_error_summary(self, action: str, output: str) -> str:
        """Return a compact notification message for a failed Git action."""
        first_line = output.splitlines()[0].strip() if output else ""
        if not first_line:
            first_line = "unknown error"
        return f"{action} failed: {first_line}"

    async def _refresh_repo_after_git_change(
        self,
        repo_root: Path,
        *,
        reload_documents: bool = False,
    ) -> None:
        """Refresh branch state, dirty markers, and open docs after a git operation."""
        self._refresh_branch_indicator()
        self._refresh_dirty_tree()
        if reload_documents:
            editor = self._main_editor_panel()
            if editor is not None:
                editor.refresh_repo_documents(
                    repo_root,
                    lambda path: self.git_service.show_file(repo_root, "HEAD", path),
                )
        self.refresh_status()

    def _sync_open_file_with_git(self, repo_root: Path, path: Path) -> None:
        """Reload one open file against disk and HEAD after a conflict action."""
        editor = self._main_editor_panel()
        if editor is None:
            return
        editor.sync_file_with_git(path, self.git_service.show_file(repo_root, "HEAD", path))
        self._refresh_dirty_tree()
        self.refresh_status()

    async def _close_git_update_tabs(self) -> None:
        """Close transient tabs created by the update/conflict workflow."""
        screen = self._active_conflict_screen()
        if screen is not None:
            screen.dismiss(None)
        editor = self._main_editor_panel()
        if editor is None:
            return
        for title in (
            "Git Conflicts",
            "git:update",
            "git:update:rebase",
            "git:update:merge",
            "git:update:continue",
            "git:update:abort",
            "git:operation:continue",
            "git:operation:abort",
        ):
            await editor.close_virtual_tab(title)

    def _active_conflict_screen(self) -> GitConflictResolverScreen | None:
        """Return the currently-open conflict screen when one is active."""
        if len(self.screen_stack) <= 1:
            return None
        top = self.screen_stack[-1]
        if isinstance(top, GitConflictResolverScreen):
            return top
        return None

    async def _show_conflict_resolver(self, repo_root: Path) -> bool:
        """Open or refresh the conflict resolver tab when a merge/rebase is active."""
        state = await asyncio.to_thread(self.git_service.conflict_state, repo_root)
        if state is None:
            screen = self._active_conflict_screen()
            if screen is not None:
                screen.dismiss(None)
            try:
                editor = self.query_one(EditorPanel)
            except Exception:
                editor = None
            if editor is not None:
                await editor.close_virtual_tab("Git Conflicts")
            self.refresh_status()
            return False
        screen = self._active_conflict_screen()
        if screen is not None:
            screen.set_state(state, repo_root)
        else:
            self._push_modal_screen(
                GitConflictResolverScreen(state, repo_root),
                callback=lambda _result: self.run_worker(self._close_git_update_tabs(), exclusive=False),
            )
        self.refresh_status()
        return True

    async def _resume_active_conflict_session(self) -> None:
        """Reopen the conflict resolver when the repo is already mid merge/rebase."""
        repo_root = await asyncio.to_thread(self._find_repo_root)
        if repo_root is None:
            return
        if await self._show_conflict_resolver(repo_root):
            self.notify(
                "A merge or rebase is already in progress. Finish it in Git Conflicts or abort it.",
                severity="warning",
            )

    async def _continue_diverged_update(self, repo_root: Path, strategy: str) -> None:
        """Continue an Update flow with an explicit merge or rebase strategy."""
        if strategy == "rebase":
            action_name = "Rebase"
            title = "git:update:rebase"
            func = self.git_service.rebase_local_commits
            progress = "Rebasing local commits onto upstream…"
            success_message = "Current branch updated via rebase"
        else:
            action_name = "Merge"
            title = "git:update:merge"
            func = self.git_service.merge_remote_changes
            progress = "Merging remote changes into current branch…"
            success_message = "Current branch updated via merge"

        self.notify(progress, severity="information")
        result = await asyncio.to_thread(func, repo_root)
        await self.open_git_output_tab(title, repo_root, result.output)

        if result.status == "success":
            await self._refresh_repo_after_git_change(repo_root, reload_documents=True)
            await self._close_git_update_tabs()
            self.notify(success_message)
            return

        if result.status == "conflict":
            await self._refresh_repo_after_git_change(repo_root, reload_documents=True)
            await self._show_conflict_resolver(repo_root)
            self.notify(
                f"{action_name} hit conflicts. Resolve them in Git Conflicts, then continue.",
                severity="warning",
            )
            return

        self.notify(self._git_error_summary(action_name, result.output), severity="error")

    async def action_git_session(self) -> None:
        """Open project-level Git actions from the top bar."""
        repo_root = self.active_repo_root()
        if repo_root is None:
            return

        branch = self.git_service.current_branch(repo_root) or "detached"
        action_id = await self.wait_for_screen_result(
            OptionPickerDialog(
                f"Git - {repo_root.name} ({branch})",
                [
                    ChoiceItem(
                        id="git.session.commit",
                        label="Commit",
                        description="Stage all changes and create a commit",
                    ),
                    ChoiceItem(
                        id="git.session.push",
                        label="Push",
                        description="Push current branch to upstream",
                    ),
                    ChoiceItem(
                        id="git.session.fetch",
                        label="Fetch",
                        description="Refresh remote refs and branch info without changing files",
                    ),
                    ChoiceItem(
                        id="git.session.update",
                        label="Update",
                        description="Fast-forward the current branch from upstream",
                    ),
                    ChoiceItem(
                        id="git.session.merge",
                        label="Merge Branch",
                        description="Merge a local or remote branch into the current branch",
                    ),
                    ChoiceItem(
                        id="git.session.branch",
                        label="Select Branch",
                        description="Browse local and remote branches",
                    ),
                    ChoiceItem(
                        id="git.session.branch_history",
                        label="Branch History",
                        description="Browse commits on the current branch",
                    ),
                ],
                placeholder="Filter git actions",
            )
        )
        if action_id is None:
            return

        if action_id == "git.session.branch_history":
            await self.action_git_branch_history()
            return

        if action_id == "git.session.update":
            if await self._show_conflict_resolver(repo_root):
                self.notify(
                    "Finish or abort the current merge/rebase before running Update again.",
                    severity="warning",
                )
                return
            self.notify("Updating current branch…", severity="information")
            result = await asyncio.to_thread(
                self.git_service.update_current_branch, repo_root
            )
            await self.open_git_output_tab("git:update", repo_root, result.output)
            if result.status == "success":
                await self._refresh_repo_after_git_change(repo_root, reload_documents=True)
                self.notify("Current branch updated")
                return
            if result.status == "diverged":
                choice = await self.wait_for_screen_result(
                    OptionPickerDialog(
                        "Current branch has diverged from upstream",
                        [
                            ChoiceItem(
                                id="git.update.rebase",
                                label="Rebase Local Commits",
                                description="Replay your local commits on top of upstream",
                            ),
                            ChoiceItem(
                                id="git.update.merge",
                                label="Merge Remote Changes",
                                description="Create a merge commit if needed",
                            ),
                            ChoiceItem(
                                id="git.update.cancel",
                                label="Cancel",
                                description="Leave the branch unchanged",
                            ),
                        ],
                        placeholder="Choose how to continue",
                    )
                )
                if choice == "git.update.rebase":
                    await self._continue_diverged_update(repo_root, "rebase")
                elif choice == "git.update.merge":
                    await self._continue_diverged_update(repo_root, "merge")
                return
            self.notify(
                self._git_error_summary("Update", result.output),
                severity="error",
            )
            return

        if action_id == "git.session.merge":
            if await self._show_conflict_resolver(repo_root):
                self.notify(
                    "Finish or abort the current merge/rebase before starting another merge.",
                    severity="warning",
                )
                return
            current_branch = self.git_service.current_branch(repo_root) or "detached"
            local_branches = set(self.git_service.list_branches(repo_root))
            branches = [
                name for name in self.git_service.list_all_branches(repo_root)
                if name != current_branch
            ]
            if not branches:
                self.notify("No mergeable branches available", severity="warning")
                return
            selected_branch = await self.wait_for_screen_result(
                OptionPickerDialog(
                    f"Merge into {current_branch}",
                    [
                        ChoiceItem(
                            id=name,
                            label=name,
                            description=(
                                "local branch"
                                if name in local_branches
                                else "remote branch"
                            ),
                        )
                        for name in branches
                    ],
                    placeholder="Filter branches to merge",
                    confirm_label="Merge",
                )
            )
            if not selected_branch:
                return
            self.notify(f"Merging {selected_branch}…", severity="information")
            result = await asyncio.to_thread(
                self.git_service.merge_branch,
                repo_root,
                selected_branch,
            )
            await self.open_git_output_tab("git:merge", repo_root, result.output)
            if result.status == "success":
                await self._refresh_repo_after_git_change(repo_root, reload_documents=True)
                self.notify(f"Merged {selected_branch} into {current_branch}")
                return
            if result.status == "conflict":
                await self._refresh_repo_after_git_change(repo_root, reload_documents=True)
                await self._show_conflict_resolver(repo_root)
                self.notify(
                    f"Merge hit conflicts. Resolve them in Git Conflicts, then continue.",
                    severity="warning",
                )
                return
            self.notify(
                self._git_error_summary("Merge", result.output),
                severity="error",
            )
            return

        if action_id == "git.session.fetch":
            self.notify("Fetching…", severity="information")
            success, output = await asyncio.to_thread(self.git_service.fetch, repo_root)
            await self.open_git_output_tab("git:fetch", repo_root, output)
            self.notify(
                "Fetch completed" if success else self._git_error_summary("Fetch", output),
                severity="information" if success else "error",
            )
            return

        if action_id == "git.session.branch":
            branches = self.git_service.list_all_branches(repo_root)
            if not branches:
                self.notify("No branches available", severity="warning")
                return
            current_branch = self.git_service.current_branch(repo_root) or "detached"
            selected_branch = await self.wait_for_screen_result(
                OptionPickerDialog(
                    "Switch branch",
                    [
                        ChoiceItem(
                            id=name,
                            label=name,
                            description="current" if name == current_branch else "",
                        )
                        for name in branches
                    ],
                    placeholder="Filter branches",
                )
            )
            if not selected_branch:
                return
            success, output = self.git_service.checkout_branch(repo_root, selected_branch)
            await self.open_git_output_tab("git:branch", repo_root, output)
            self.notify(
                f"Switched to {selected_branch}" if success else "Branch switch failed",
                severity="information" if success else "error",
            )
            return

        if action_id == "git.session.commit":
            if self.git_service.conflict_state(repo_root) is not None:
                await self._show_conflict_resolver(repo_root)
                self.notify(
                    "A merge or rebase conflict is still in progress. Resolve or abort it before using Commit.",
                    severity="warning",
                )
                return
            result = await self.wait_for_screen_result(
                GitCommitScreen(repo_root, self.git_service)
            )
            if not result:
                return
            message, push_after = result
            success, output = await asyncio.to_thread(
                self.git_service.commit_all, repo_root, str(message)
            )
            await self.open_git_output_tab("git:commit", repo_root, output)
            if success:
                self._refresh_dirty_tree()
                try:
                    self.query_one(EditorPanel).mark_all_as_clean()
                except Exception:
                    pass
                if push_after:
                    self.notify("Pushing…", severity="information")
                    push_success, push_output = await asyncio.to_thread(
                        self.git_service.push, repo_root
                    )
                    await self.open_git_output_tab("git:push", repo_root, push_output)
                    if push_success:
                        await self._close_git_output_tabs("git:commit", "git:push")
                        self.notify("Commit created and pushed")
                    else:
                        await self._close_git_output_tabs("git:commit")
                        first_line = (
                            push_output.splitlines()[0] if push_output else "unknown error"
                        )
                        self.notify(
                            f"Commit created, but push failed: {first_line}",
                            severity="error",
                        )
                else:
                    await self._close_git_output_tabs("git:commit")
                    self.notify("Commit created")
            else:
                first_line = output.splitlines()[0] if output else "unknown error"
                self.notify(f"Commit failed: {first_line}", severity="error")
            return

        if action_id == "git.session.push":
            entries = self.git_service.push_preview_entries(repo_root)
            if not entries:
                self.notify("No unpushed commits to push", severity="information")
                return
            confirmed = await self.wait_for_screen_result(
                GitPushScreen(repo_root, self.git_service, entries)
            )
            if not confirmed:
                return
            self.notify("Pushing…", severity="information")
            success, output = await asyncio.to_thread(self.git_service.push, repo_root)
            await self.open_git_output_tab("git:push", repo_root, output)
            if success:
                await self._close_git_output_tabs("git:push")
            self.notify(
                "Push completed" if success else self._git_error_summary("Push", output),
                severity="information" if success else "error",
            )
            return

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

    async def action_git_branch_history(self) -> None:
        """Open an interactive commit log for the current branch."""
        repo_root = self.active_repo_root()
        if repo_root is None:
            return
        branch = self.git_service.current_branch(repo_root) or "HEAD"
        entries = self.git_service.branch_history(repo_root)
        if not entries:
            self.notify("No commits found in this repository", severity="warning")
            return
        workspace_panel = self.query_one("#workspace-panel")
        if workspace_panel.display:
            workspace_panel.display = False
            self._workspace_hidden_for_git_log = True
        terminal_panel = self.query_one("#terminal-panel")
        if terminal_panel.display:
            terminal_panel.display = False
            self._terminal_hidden_for_git_log = True
        self.sync_splitter_visibility()
        self.refresh_status()
        view = GitHistoryBrowserView(
            branch=branch,
            entries=entries,
            repo_root=repo_root,
            git_service=self.git_service,
        )
        await self.query_one(EditorPanel).open_widget_tab("Git Log", view, always_replace=True)
        self.refresh_status()

    async def on_git_log_view_commit_selected(self, event: GitLogView.CommitSelected) -> None:
        """Open a changed-files tab when the user picks a commit from the log."""
        commit = event.commit
        repo_root = event.repo_root
        file_entries = self.git_service.files_changed_in_commit(repo_root, commit)
        if not file_entries:
            self.notify(f"No file changes recorded for {commit[:8]}", severity="information")
            return
        view = GitChangedFilesView(
            commit=commit,
            subject=event.subject,
            file_entries=file_entries,
            repo_root=repo_root,
        )
        await self.query_one(EditorPanel).open_widget_tab(
            f"Commit {commit[:8]}", view, always_replace=True
        )
        self.refresh_status()

    async def on_git_conflict_resolver_view_refresh_requested(
        self,
        event: GitConflictResolverView.RefreshRequested,
    ) -> None:
        """Reload the conflict resolver from current disk and git state."""
        await self._show_conflict_resolver(event.repo_root)
        self._refresh_dirty_tree()

    async def on_git_conflict_resolver_view_apply_edited_result(
        self,
        event: GitConflictResolverView.ApplyEditedResult,
    ) -> None:
        """Write the edited result pane back to the conflicted file."""
        success, output = await asyncio.to_thread(
            self.git_service.write_worktree_file,
            event.repo_root,
            event.filepath,
            event.text,
        )
        if not success:
            self.notify(output, severity="error")
            return
        self._sync_open_file_with_git(event.repo_root, event.repo_root / event.filepath)
        await self._show_conflict_resolver(event.repo_root)
        self.notify(output)

    async def on_git_conflict_resolver_view_edit_manually(
        self,
        event: GitConflictResolverView.EditManually,
    ) -> None:
        """Open the conflicted file for manual editing."""
        path = event.repo_root / event.filepath
        if not path.exists():
            self.notify("This conflicted file is not present in the working tree.", severity="error")
            return
        await self._open_location(path, event.start_line, 1)
        self.notify(
            "Opened the real conflicted file. Git markers in that file are expected until you finish resolving or abort the operation.",
            severity="information",
        )

    async def on_git_conflict_resolver_view_mark_resolved(
        self,
        event: GitConflictResolverView.MarkResolved,
    ) -> None:
        """Stage a manually resolved file and refresh conflict state."""
        success, output = await asyncio.to_thread(
            self.git_service.mark_conflict_resolved,
            event.repo_root,
            event.filepath,
        )
        if not success:
            self.notify(output, severity="error")
            return
        self._sync_open_file_with_git(event.repo_root, event.repo_root / event.filepath)
        await self._show_conflict_resolver(event.repo_root)
        self.notify(output)

    async def on_git_conflict_resolver_view_continue_requested(
        self,
        event: GitConflictResolverView.ContinueRequested,
    ) -> None:
        """Continue the active merge or rebase after resolution."""
        self.notify("Continuing git operation…", severity="information")
        result = await asyncio.to_thread(
            self.git_service.continue_conflict_operation,
            event.repo_root,
        )
        await self.open_git_output_tab("git:operation:continue", event.repo_root, result.output)
        if result.status == "success":
            await self._refresh_repo_after_git_change(event.repo_root, reload_documents=True)
            await self._close_git_update_tabs()
            self.notify("Git operation completed")
            return
        if result.status == "conflict":
            await self._refresh_repo_after_git_change(event.repo_root, reload_documents=True)
            await self._show_conflict_resolver(event.repo_root)
            self.notify("More conflicts need resolution before this git operation can finish.", severity="warning")
            return
        self.notify(self._git_error_summary("Continue", result.output), severity="error")

    async def on_git_conflict_resolver_view_abort_requested(
        self,
        event: GitConflictResolverView.AbortRequested,
    ) -> None:
        """Abort the active merge or rebase and restore the repo to a clean branch state."""
        self.notify("Aborting git operation…", severity="information")
        result = await asyncio.to_thread(
            self.git_service.abort_conflict_operation,
            event.repo_root,
        )
        await self.open_git_output_tab("git:operation:abort", event.repo_root, result.output)
        if result.status == "success":
            await self._refresh_repo_after_git_change(event.repo_root, reload_documents=True)
            await self._close_git_update_tabs()
            self.notify("Git operation aborted")
            return
        self.notify(self._git_error_summary("Abort", result.output), severity="error")

    async def on_editor_panel_virtual_tab_closed(
        self,
        event: EditorPanel.VirtualTabClosed,
    ) -> None:
        """When Git Conflicts closes, clean up the rest of the transient update tabs."""
        if event.title == "Git Log" and self._workspace_hidden_for_git_log:
            workspace_panel = self.query_one("#workspace-panel")
            if not workspace_panel.display:
                workspace_panel.display = True
            self._workspace_hidden_for_git_log = False
        if event.title == "Git Log" and self._terminal_hidden_for_git_log:
            terminal_panel = self.query_one("#terminal-panel")
            if not terminal_panel.display:
                terminal_panel.display = True
            self._terminal_hidden_for_git_log = False
        if event.title == "Git Log":
            self.sync_splitter_visibility()
            self.refresh_status()
        if event.title != "Git Conflicts":
            return
        await self._close_git_update_tabs()

    async def on_git_history_browser_view_close_requested(
        self,
        _event: GitHistoryBrowserView.CloseRequested,
    ) -> None:
        """Close the single-tab branch history workflow from its top-level Escape."""
        await self.query_one(EditorPanel).close_virtual_tab("Git Log")
        self.refresh_status()

    async def on_git_changed_files_view_file_selected(
        self, event: GitChangedFilesView.FileSelected
    ) -> None:
        """Open a delta diff when the user picks a file from a commit's change list."""
        commit = event.commit
        repo_root = event.repo_root
        filepath = event.filepath
        old_filepath = event.old_filepath
        status = event.status
        short = commit[:8]

        if status == "A":
            before_text = ""
            before_label = "/dev/null"
        else:
            src = old_filepath if old_filepath else filepath
            before_raw = self.git_service.show_file(repo_root, f"{commit}~1", repo_root / src)
            before_text = before_raw if before_raw is not None else ""
            before_label = f"{short}~1:{src}"

        if status == "D":
            after_text = ""
            after_label = "/dev/null"
        else:
            after_raw = self.git_service.show_file(repo_root, commit, repo_root / filepath)
            after_text = after_raw if after_raw is not None else ""
            after_label = f"{short}:{filepath}"

        filename = Path(filepath).name
        await self.query_one(EditorPanel).open_diff_tab(
            f"{short}:{filename}",
            before_label,
            before_text,
            after_label,
            after_text,
        )
        self.refresh_status()

    async def action_git_changed_files(self) -> None:
        """Pick a file changed vs HEAD and open it in a side-by-side diff tab."""
        repo_root = self.active_repo_root()
        if repo_root is None:
            return
        changed = self.git_service.list_changed_files(repo_root)
        if not changed:
            self.notify("No changed files found vs HEAD", severity="information")
            return
        choice = await self.wait_for_screen_result(
            OptionPickerDialog(
                "Changed files",
                [ChoiceItem(id=str(p), label=str(p.relative_to(repo_root))) for p in changed],
                placeholder="Filter files",
            )
        )
        if not choice:
            return
        target = Path(choice)
        old_text = self.git_service.show_file(repo_root, "HEAD", target) or ""
        try:
            new_text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            new_text = ""
        rel = str(target.relative_to(repo_root))
        await self.query_one(EditorPanel).open_diff_tab(
            f"changed:{target.name}",
            f"HEAD:{rel}",
            old_text,
            f"working tree:{rel}",
            new_text,
        )
        self.refresh_status()

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
                "Compare With Branch",
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

    async def action_git_diff_remote(self) -> None:
        """Open an upstream remote diff tab for the active file."""
        context = self.active_file_context()
        if context is None:
            return
        path, repo_root = context
        upstream = self.git_service.upstream_ref(repo_root)
        if not upstream:
            self.notify("Current branch has no upstream remote", severity="warning")
            return

        other = self.git_service.show_file(repo_root, upstream, path)
        if other is None:
            self.notify("Unable to read file from the current branch upstream", severity="error")
            return
        current = path.read_text(encoding="utf-8", errors="replace")
        await self.query_one(EditorPanel).open_diff_tab(
            f"diff:{path.name}:{upstream}",
            f"{upstream}:{path.name}",
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
        cursor = self.query_one(EditorPanel).active_cursor()
        prefill = f"{cursor[0]}:{cursor[0]}" if cursor else ""
        value = await self.wait_for_screen_result(
            PromptDialog("Line history", placeholder="start:end, e.g. 10:20", value=prefill)
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

    async def action_python_outline(self) -> None:
        """Show semantic structure for the active Python file."""
        editor = self.query_one(EditorPanel)
        path = editor.active_path
        text = editor.active_text
        if path is None or text is None:
            self.notify("Open a Python file first", severity="warning")
            return
        if not self.python_semantic.available_for(path):
            self.notify("Semantic outline currently supports Python files", severity="warning")
            return
        report = self.python_semantic.build_outline(path, text)
        await editor.open_readonly_tab(f"python-outline:{path.name}", report)

    async def action_python_symbol_details(self) -> None:
        """Show definitions and usages for the symbol under the cursor."""
        editor = self.query_one(EditorPanel)
        path = editor.active_path
        text = editor.active_text
        cursor = editor.active_cursor()
        if path is None or text is None or cursor is None:
            self.notify("Open a Python file first", severity="warning")
            return
        if not self.python_semantic.available_for(path):
            self.notify("Symbol details currently support Python files", severity="warning")
            return
        report = self.python_semantic.symbol_report(path, text, cursor[0], cursor[1])
        await editor.open_readonly_tab(f"python-symbol:{path.name}", report)

    async def action_code_goto_definition(self) -> None:
        """Perform the current definition action with LSP/AI fallback."""
        if await self._run_python_navigation("Definition", "definition"):
            return
        await self._run_code_intelligence("definition")

    async def action_code_find_references(self) -> None:
        """Find all references to a symbol across the workspace via regex search."""
        if await self._run_python_navigation("References", "references"):
            return
        symbol = await self.wait_for_screen_result(
            PromptDialog("Find references", placeholder="symbol name")
        )
        if not symbol:
            return
        symbol = symbol.strip()
        if not symbol:
            return

        raw_matches = self.search_service.search_workspace_text(
            self.workspace_state.roots, symbol
        )
        # Parse "path:line: snippet" tuples
        results: list[tuple[str, int, int, str]] = []
        for match in raw_matches:
            try:
                path_part, rest = match.split(":", 1)
                line_part, snippet = rest.split(": ", 1)
                results.append((path_part, int(line_part), 1, snippet.strip()))
            except (ValueError, IndexError):
                continue

        selection = await self.wait_for_screen_result(
            FindReferencesScreen(symbol, results)
        )
        if selection is None:
            return

        path_str, line, column = selection
        await self._open_location(Path(path_str), line, column)

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

    async def _run_python_navigation(self, title: str, intent: str) -> bool:
        """Attempt Python navigation from the current cursor location."""
        editor = self.query_one(EditorPanel)
        path = editor.active_path
        text = editor.active_text
        cursor = editor.active_cursor()
        if (
            path is None
            or text is None
            or cursor is None
            or not self.python_navigation.available_for(path)
        ):
            return False

        symbol = self.python_semantic.symbol_at_position(text, cursor[0], cursor[1])
        if symbol is None:
            self.notify("Move the cursor onto a Python symbol first", severity="warning")
            return True

        if intent == "definition":
            targets = self.python_navigation.goto_definition(
                path,
                text,
                cursor[0],
                cursor[1],
                self.workspace_state.roots,
            )
        else:
            targets = self.python_navigation.find_references(
                path,
                text,
                cursor[0],
                cursor[1],
                self.workspace_state.roots,
            )

        if not targets:
            self.notify(f"No {intent} found for {symbol}", severity="warning")
            return True

        await self._present_python_navigation_results(title, symbol, targets)
        return True

    async def _present_python_navigation_results(
        self,
        title: str,
        symbol: str,
        targets: list[PythonNavigationTarget],
    ) -> None:
        """Open a single target directly or prompt the user to choose one."""
        if len(targets) == 1:
            target = targets[0]
            await self._open_location(target.path, target.line, target.column)
            return

        self.push_screen(
            FindReferencesScreen(
                symbol,
                [
                    (str(target.path), target.line, target.column, target.preview)
                    for target in targets
                ],
                title=title,
            )
        )

    async def _present_location_results(
        self,
        title: str,
        query: str,
        results: list[tuple[str, int, int, str]],
    ) -> None:
        """Open one location directly or present a lightweight result picker."""
        if not results:
            self.notify(f"No matches found for {query}", severity="warning")
            return

        if len(results) == 1:
            path_str, line, column, _snippet = results[0]
            await self._open_location(Path(path_str), line, column)
            return

        self.push_screen(FindReferencesScreen(query, results, title=title))

    def on_find_references_screen_location_opened(
        self,
        message: FindReferencesScreen.LocationOpened,
    ) -> None:
        """Open a selected search result while keeping the result popup visible."""
        self.run_worker(
            self._open_location(Path(message.path_str), message.line, message.column),
            exclusive=False,
        )

    async def _run_workspace_text_search(
        self,
        query: str,
        *,
        title: str = "Text Search",
        case_sensitive: bool = False,
    ) -> None:
        """Search text across workspace roots and present openable results."""
        normalized = query.strip()
        if not normalized:
            return
        results = self.search_service.search_workspace_text_locations(
            self.workspace_state.roots,
            normalized,
            case_sensitive=case_sensitive,
        )
        await self._present_location_results(title, normalized, results)

    async def _run_workspace_name_search(self, query: str, *, case_sensitive: bool = False) -> None:
        """Search file names and lightweight Python symbol names."""
        normalized = query.strip()
        if not normalized:
            return
        results = self.search_service.search_workspace_names(
            self.workspace_state.roots,
            normalized,
            case_sensitive=case_sensitive,
        )
        await self._present_location_results("Name Search", normalized, results)

    async def _open_location(self, path: Path, line: int, column: int) -> None:
        """Open a file and move the cursor to a 1-based line and column."""
        await self._open_editor_file(path)
        editor = self._main_editor_panel()
        if editor is None:
            return
        text_area = editor.active_text_area
        if text_area is None:
            return
        try:
            text_area.cursor_location = (max(0, line - 1), max(0, column - 1))
            text_area.scroll_cursor_visible()
        except Exception:
            pass

    def apply_panel_widths(self) -> None:
        """Apply current panel widths."""
        self.query_one("#workspace-panel").styles.width = self.workspace_width
        self.query_one("#terminal-panel").styles.width = self.terminal_width
        self.config.workspace_width = self.workspace_width
        self.config.terminal_width = self.terminal_width
        self.config.default_workspace = str(self.workspace_state.roots[0])
        self.config_store.save(self.config)

    def sync_splitter_visibility(self) -> None:
        """Keep splitters aligned with panel visibility."""
        workspace_visible = self.query_one("#workspace-panel").display
        terminal_visible = self.query_one("#terminal-panel").display
        editor_visible = self.query_one("#editor-panel").display
        self.query_one("#workspace-splitter").display = workspace_visible and editor_visible
        self.query_one("#terminal-splitter").display = terminal_visible and editor_visible

    def adjust_workspace_by(self, delta: int) -> None:
        """Resize the workspace panel by a drag delta."""
        self.workspace_width = min(60, max(20, self.workspace_width + delta))
        self.apply_panel_widths()

    def adjust_terminal_by(self, delta: int) -> None:
        """Resize the terminal panel by a drag delta."""
        self.terminal_width = min(60, max(24, self.terminal_width - delta))
        self.apply_panel_widths()

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
