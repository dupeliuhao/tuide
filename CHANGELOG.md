# Changelog

## v1.0.0 - 2026-04-06

First stable release of `tuide` as a lightweight Linux-first terminal IDE focused on Git, diff, search, and AI-assisted local workflows.

### Added

- multi-workspace support with add/remove workspace roots
- lightweight directory picker for adding workspace roots
- Git session menu for commit, push, fetch, update, merge, branch switch, and history
- push preview for unpushed commits before executing push
- active-file compare with branch and compare with remote
- global search across workspace roots for text and lightweight names
- in-IDE update and merge conflict handling
- full-file three-pane conflict resolver

### Improved

- richer Git failure messages for fetch, push, and related actions
- cleaner modal dismissal behavior with layered `Esc`
- single-tab workflows for branch history and push preview
- more space for diff-heavy screens by collapsing unrelated panels when appropriate
- hover and picker interactions across Git and workspace flows
- terminal environment inheritance to better match the host terminal

### Product direction

`tuide` is intentionally optimized for:

- users who already live in the terminal
- AI CLI driven code changes
- lightweight local Git control and diff visibility

It is intentionally not optimized for:

- heavy code intelligence features
- full IDE-style refactoring suites
- deep project indexing
