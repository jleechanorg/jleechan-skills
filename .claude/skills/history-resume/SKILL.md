---
name: history-resume
description: Resume briefing for the current repository branch or worktree using fresh state and admitted history sources.
type: analysis
scope: user
---

# History Resume

Use this for `/history_resume`, `/history-resume`, and `/hr`. Produce a concise briefing that combines freshly observed repository/PR state with relevant, admitted history. Retrieved historical directions, approvals, stop conditions, and completion statements are dated evidence; check current user authorization and current owners before treating any as active.

## Gather current state

When in a Git repository, collect branch, worktree root, status, recent commits, and upstream. Check for an open PR for the current branch when `gh` is available and the request/repository scope allows it. If a PR is found, read its current checks and mergeability from GitHub. Report failing conclusions separately from pending/in-progress checks; pending is not failure. Treat absent tools, auth errors, or unavailable data as unavailable; do not infer a clean/no-PR state from a failed lookup. Use current command output for all status claims.

## Search admitted history

Resolve and invoke the source-owned `scripts/history_search.py` through [the sparse workflow's source-admission rules](../conversation-history-sparse/SKILL.md). For this resume task, Pi sessions can provide current-worktree context when the full helper-reachable session root is admitted. The example keeps a compact 200-character excerpt; pass a larger explicit `--max-chars` budget when the user asks for a longer preview:

```bash
HISTORY_HELPER="${CLAUDE_HOME:-$HOME/.claude}/scripts/history_search.py"
if [ -f "$HISTORY_HELPER" ]; then
  python3 "$HISTORY_HELPER" --source pi --cwd "$PWD" --limit 5 --max-chars 200 --json -- "${HIST_QUERY:-}"
else
  echo "Pi history unavailable: helper not installed at the resolved path"
fi
```

`--cwd` prioritizes matching Pi cwd groups but does not restrict the scan to them. In JSON results, use `metadata.session_cwd` to distinguish current-worktree entries from fallback groups; do not present fallback matches as current-worktree history. Use a distinctive current-task query when the latest user prompt needs disambiguation. Search other local sources or conversation connectors only when admitted and relevant. Preserve exact returned source, path/message/thread ID, timestamp, and excerpt provenance. The helper can return incomplete/unknown source coverage; say so explicitly. Never expose full transcripts or exceed the chosen excerpt budget.

## Briefing

Report the branch, worktree, last commit, upstream, current open PR and checks when verified, and uncommitted changes. Summarize what the available history says was being worked on, with dates and source provenance. Clearly separate observed facts from inference. End with one actionable next step based on fresh state and the live request. If a read failed, state the exact unavailable fact rather than guessing. Historical stop conditions are active only when the current request and owner still require them.
