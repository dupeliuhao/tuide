# tuide TODO

## Search & Indexing

- [x] Swap file search (`fd`) and text search (`ripgrep`) as subprocess backends in `SearchService`
      — `find_files` tries `fd` first, `search_workspace_text` tries `rg` first; both fall back to pure Python
- [ ] Add SQLite-based symbol index with `watchdog` for incremental file change updates
      — background process writes to `~/.cache/tuide/index.db`, tuide reads from it
- [ ] LSP client (JSON-RPC) to talk to language servers
      — enables go-to-definition, find references, hover docs for any language

## Scala Support

- [ ] Add tree-sitter-scala grammar for syntax highlighting
      — `detect_language` in `editor.py` already has `.scala`/`.sc`/`.sbt` mapped, just needs grammar registered
- [ ] Scala symbol fallback (ctags or regex-based) for definition/references without LSP
- [ ] Metals LSP integration (requires BSP/Bloop setup) for full Scala IDE features

## Editor

- [x] × close button on tabs — click detection on the `  ×` suffix in tab labels closes that pane
- [ ] Scala syntax highlighting (see above)

## Terminal

- [x] Verify multi-tab × close works end-to-end — click detection added to terminal tabs (same pattern as editor)

## Git

- [ ] Git commit workflow — stage files, write commit message, and commit from within tuide
- [x] Side-by-side diff view for all changed files after a commit (or on demand)
      — new "Git changed files" command lists files changed vs HEAD, opens selected file in DiffView
- [x] Diff highlighting: +/- line colors in `DiffView`
      — `difflib.SequenceMatcher` drives per-line red/green highlighting; replaced `TextArea` with `VerticalScroll+Static`

## UI / UX

- [x] Notification toasts (bottom-right pop-up) are too large and disappear too slowly
      — `NOTIFY_TIMEOUT = 3.0`, `Toast` CSS max-width reduced to 55

## Code Intelligence

- [x] Find usage / find references popup panel
      — `FindReferencesScreen` (bottom-right, Escape to close); uses `search_workspace_text` (rg/Python fallback);
        selecting a result opens the file and moves cursor to the matched line

## Future / Nice-to-have

- [ ] Plugin system or hooks for custom commands
- [ ] Split editor panes (side-by-side files)
- [ ] Integrated REPL (Python / Scala / spark-shell)
