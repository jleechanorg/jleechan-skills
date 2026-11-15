# cmux metadata snapshot contract

These read-only protocol forms and field names are retained from the reviewed
source. Check installed-version support before use. `$SOCK` is a verified
socket on the owning computer, never an arbitrary matching file.

## Query forms

```bash
# Inventory on the selected instance
printf '{"method":"workspace.list","params":{}}\n' | nc -U "$SOCK"

# Replace the illustrative UUID via a JSON encoder, not shell interpolation.
printf '{"method":"surface.list","params":{"workspace_id":"<uuid>"}}\n' | nc -U "$SOCK"

# Legacy read-only sidebar query, only for an API-returned validated UUID.
printf 'sidebar_state --tab=<workspace_uuid>\n' | nc -U "$SOCK"
```

Use the runtime's supported bounded socket client and response/error handling;
`nc` availability and flags vary. A timeout or malformed response is a failure,
not an empty inventory. If the installed CLI offers an equivalent verified
read-only JSON interface, prefer it to assembling raw socket traffic.

## Source fields to retain

| Scope | Fields | Source |
| --- | --- | --- |
| Workspace | `id`, `title`, `index`, `selected`, `current_directory` | `workspace.list` |
| Sidebar | `cwd`, `focused_cwd`, `git_branch`, `pr`, `pr_label` | `sidebar_state` |
| Surface | `id`, `title`, `type`, `pane_id` | `surface.list` |

Preserve missing/unknown separately from an empty value. Do not concatenate
different CWD fields or silently pick one as authoritative. Surface metadata
does not necessarily identify that surface's actual shell CWD. A restore
planner must disclose any workspace-level CWD fallback.

The source shape is a JSON object containing `timestamp`, `socket`,
`workspace_count`, and `workspaces`; each workspace contains its fields above
plus a `surfaces` array. Example using synthetic values:

```json
{
  "timestamp": "<UTC capture time>",
  "socket": "<verified local socket path>",
  "workspace_count": 1,
  "workspaces": [{
    "id": "<workspace UUID>",
    "title": "example-workspace",
    "index": 0,
    "selected": false,
    "current_directory": "/example/project",
    "cwd": "/example/project",
    "focused_cwd": "/example/project",
    "git_branch": "example-branch",
    "pr": "",
    "pr_label": "",
    "surfaces": [{
      "id": "<surface UUID>",
      "title": "example-shell",
      "type": "terminal",
      "pane_id": "<pane UUID>"
    }]
  }]
}
```

A new producer should explicitly version its schema and add capture errors,
requested scope, window metadata, and completeness status. A legacy helper
may not accept those extensions: validate compatibility rather than claiming
the file is restorable by an unreviewed script. Do not execute data from a
backup, restore its socket path blindly, or treat saved IDs as current IDs.
