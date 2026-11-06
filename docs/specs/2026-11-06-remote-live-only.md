# PR #703 — remote live-only drift scan specification (draft)

## Outcome
`report --remote HOST` reports live files absent from the tracked config scope, with the same root containment and symlink privacy rules as local reporting. It must not present a partial or failed enumeration as complete.

## Non-goals
- Do not change tracked-file comparison, its expected-record-count contract, or `apply` behavior.
- Do not follow symlinks or disclose hashes, sizes, contents, or target paths for symlinked roots/files.
- Do not write to remote hosts or change remote homes, repositories, credentials, or SSH configuration.
- Do not scan beyond roots selected by `scope_live_roots(files, full)`.

## Acceptance criteria
1. The remote walk discovers untracked regular files inside selected live roots and excludes the existing noise filters.
2. A symlink at the root, any parent component, or a discovered leaf is represented only as `symlink`; no target descendants or metadata are returned.
3. A regular live-only file inside an independent repository carries the existing remote repository-root and last-commit metadata when that lookup succeeds; symlink records carry neither.
4. Any incomplete `find`/enumeration is reported as incomplete through the caller's warning path, while preserving both successful tracked-file results and live-only rows read before the error. No partial walk may look like a clean complete scan.
5. Missing roots remain empty results; output parsing preserves all paths and record boundaries without changing tracked-file results.

## User story
No user-facing product UI changes. Operators running `report --remote` can see untracked configuration drift, distinguish symlinked paths without learning their targets, and recognize an incomplete scan.

## Proof plan
Run focused unit/behavioral tests using a controlled fake SSH executable and temporary remote-home tree. Cover a regular live-only leaf, excluded noise, a nested independent repository, symlink root/parent/leaf, absent root, malformed/large path boundaries, and a `find` failure. Then run the repository's focused sync-live-config suite. Separately run the existing owned SSH fixture on `jeff-ubuntu` against a task-owned Scratch home to confirm transport and output; never inspect or mutate a real home.

## Mock / fixture rationale
The unit layer mocks SSH only to exercise generated command construction, parsing, failure reporting, and containment. A separate owned-host fixture with real SSH/SCP validates that the submitted script runs through the actual transport without touching user data.

## Risk and mitigation
The change executes a read-only remote `find` over configured roots and returns filenames. A symlink or partial-walk error could disclose paths outside scope or falsely imply no drift. Check every root component before traversal, keep leaf metadata withheld, and surface incomplete traversal as a warning/status that cannot be confused with a complete clean scan.
