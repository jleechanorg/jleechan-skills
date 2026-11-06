# Sync live configuration tool

## Outcome

Provide a safe, efficient way for skills maintainers to compare repository configuration with live configuration, preview explicitly named local copies, and inspect full-scope drift without spending time in unrelated runtime state or unrelated Git history.

## Non-goals

- Do not infer which side is fresher or choose an apply direction. The caller makes that decision.
- Do not add an automatic sync, a remote dry-run, or a remote live-only directory scan.
- Do not change player-facing application behavior, gameplay, UI, or model calls.

## Acceptance

- `report --full` compares tracked files with live files and lists live-only files, except directory trees whose path component appears in `RUNTIME_DIRS`.
- Batched commit metadata matches `git log -1` for requested files. The batched lookup uses literal pathspecs limited to the requested top-level subtrees or root files.
- For valid paths, local `apply --dry-run` prints source and effective destination absolutes, the planned action, and full hashes where available. It uses `dst=missing` when a create is planned, performs no writes or directory creation, and returns nonzero when a path fails validation.
- Repository paths stay under their mapped root. The only cross-root exception is a tracked `hermes/skills/<path>` link whose resolved target is the matching `.claude/skills/<path>`; every symlink component in that alias must be Git-tracked.
- Remote repo-to-live apply packages the resolved file contents under the requested path for the permitted Hermes-to-Claude skill alias.

## User stories

No player-facing UI or gameplay change.

As a skills maintainer, I can see the exact paths, actions, and hashes before applying a local copy. Before this change, the tool had no local preview. Now `--dry-run` shows the planned copy without writing.

As a maintainer running `report --full`, I can inspect drift without traversing known runtime trees or starting one Git process per path.

## Proof plan

- From the checkout, run `PYTHONPATH=<checkout> python3 -m pytest -q <checkout>/tests/test_sync_live_config.py` for path mapping, tracked and untracked symlinks, cached commit metadata, dry-run output and immutability, and remote archive member contents.
- Run `report --full --json` against an owned temporary home containing live-only fixture files and a runtime sentinel. Confirm the report completes, includes expected live-only files, omits the sentinel, and returns commit metadata for tracked files.
- Run local dry-run scenarios in both directions against an owned fixture home. Check hashes, mtimes, and destination absence before and after.
- Exercise remote repo-to-live apply with a tracked Hermes symlink and an owned remote Scratch home. Compare the remote destination hash with the expected fixture bytes.
- Run `ruff check --ignore E741 scripts/sync_live_config.py tests/test_sync_live_config.py` and `git diff --check`. E741 in `git_tracked_files` predates this PR.

## Mock or justified exemption

Tests use temporary Git repositories and home directories. The remote archive unit test stubs only SSH/SCP to inspect the tar member; a separate fixture run uses actual SSH/SCP to an owned Scratch home. No LLM, application, player, or UI mock is needed.

## Risk

`RUNTIME_DIRS` still filters directory basenames at every depth. A bounded live-host check found no concrete syncable configuration path omitted by this filter; Bead `bd-sync-live-config-live-only-pruning-bh5` tracks follow-up investigation. Remote dry-run and the remote live-only directory scan remain outside this scope.
