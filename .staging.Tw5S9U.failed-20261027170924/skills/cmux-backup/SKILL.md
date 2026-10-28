---
name: cmux-backup
description: Capture an authorized cmux workspace inventory, surface metadata, working directories, and git sidebar state to a private timestamped JSON backup.
---

# cmux-backup

Create a read-only cmux metadata snapshot on the computer running cmux.
Backup does not imply restore, terminal input, agent communication, focus
changes, or process control. An inspection-only request does not imply writing
a backup unless that output is part of the task.

## Resolve the instance and scope

Use the supported authorized-computer route for the user's Mac; a cloud skill
cannot directly access its Unix socket. Verify the active cmux CLI/build and
local socket metadata before a query. Respect the user-named instance, window,
and workspace subset. An unqualified request to back up all cmux workspaces
includes all workspaces on the selected instance, not every discovered socket.

The source used `$CMUX_SOCKET` for a raw Unix-socket client and
`CMUX_SOCKET_PATH` for the CLI. These are separate conventions; verify which
the installed runtime uses. Do not choose an arbitrary `/tmp/cmux*.sock`,
hardcode a dev-build tag, or silently switch instances. A historical default
was `$HOME/Library/Application Support/cmux/cmux.sock`; use it only if local
metadata confirms it belongs to the intended instance.

Inspect the supported `cmux identify --json` and `cmux tree --all` output to
record current identity and any window association exposed by this build.
No caller block is acceptable for inventory, but it does not identify an
implicit “my session” target. Preserve window identity when available; mark it
unknown rather than inventing relationships absent from the source API.

## Capture metadata

Read [snapshot-contract.md](references/snapshot-contract.md) for the retained
read-only RPCs and schema. Query workspaces, then surfaces and sidebar state
for each selected workspace UUID. Keep source-provided IDs, title, index,
selected state, CWD variants, git branch, and PR metadata. Do not read terminal
contents, shell history, environment values, or agent transcripts.

The original `cmux-backup.sh` is not bundled or validated here. Do not execute
a discovered helper because its filename matches. Use a separately reviewed
runtime adapter or verified read-only protocol implementation. If neither is
available, report that inventory/snapshot execution is blocked; do not claim
a backup from this Markdown alone.

Record per-query errors and unavailable fields. A workspace can change during
capture; retain capture time and instance identity and report inconsistent or
partial results. Do not silently replace a failed query with an empty list.

## Write and verify the backup

Use the user's requested private destination. Otherwise preserve the source
convention `$HOME/.cmux-backups/cmux-backup-<timestamp>.json` only when the
executor has permission to write there. Use an unambiguous timestamp and a
unique name; never overwrite another snapshot. A permitted task-local output
is a fallback, with its location reported accurately.

Write atomically with restrictive local access where supported. Verify that
the final file parses as JSON, workspace/surface counts match successful
queries, required metadata is present, and query failures are explicit. Do
not claim an atomic application snapshot: the queries are sequential.

Report file location, timestamp, selected instance/scope, captured counts,
and omissions. Summarize private paths/PR details only as needed for the user.
The backup itself can disclose project names, directories, and PR identities;
do not upload, publish, or share it merely because creating it was authorized.

## Restoration boundary

[cmux-restore](../cmux-restore/SKILL.md) can preview a selected backup and, when
requested, restore missing workspaces. A metadata snapshot does not preserve
running processes, live shell state, terminal scrollback, agent sessions,
browser authentication, or an exact pane layout. Never claim those were saved.
