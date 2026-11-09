# Specialized history recovery (on demand)

Begin with [the sparse workflow](../../conversation-history-sparse/SKILL.md) for source admission, provenance, excerpt budgets, and coverage language. These procedures do not grant access to sources or repositories. Keep each source's results distinct from supported-helper coverage.

Use this reference only when the user explicitly requests one of these procedures, or when admitted supported-source results are insufficient and the procedure is relevant. Before running any query, verify that the required path is admitted. If the needed bounded route or tool is unavailable, report that source as unavailable/not searched; do not widen access or silently skip a requested filter.

## Antigravity Markdown exports

This is distinct from the helper's agy CLI database/brain-log source. Use it only when the user explicitly requests exported Antigravity Markdown or admitted helper results are insufficient and these exports are relevant. Resolve the directory only from the registered `ANTIGRAVITY_EXPORT_DIR` variable in [the portability registry](../../../../docs/portability-env-vars.md); if unset or not a directory, report unavailable/not searched. A configured value still needs source admission. Do not guess a Dropbox path or inspect backups, credentials, or other Antigravity stores.

Within the admitted directory, inspect only top-level `*.md` files, ordered by modification time, and cap the candidate sample at 50 files and matching previews at 20 (or smaller requested limits). Search the query as a literal case-insensitive substring. Return a bounded excerpt around the match, the exact file path, and the file's mtime-derived date; keep the legacy excerpt at 150 characters unless a larger preview was requested. Because this is a bounded file sample without complete coverage metadata, report zero returned matches as coverage unverified, not no-match. Do not recurse or expand the candidate set without a larger authorized scope.

## OpenCode session-diff files

The source is `~/.local/share/opencode/storage/session_diff/`, unless the user has identified an admitted equivalent. Search only top-level `*.json` files in that directory, ordered newest-first by mtime. Inspect no more than 50 candidate files and return no more than 20 matching files (or the smaller requested limit). Use the query as data, retain a bounded substring around each match, and report the exact path, file ID/name, and mtime-derived date. The legacy preview is 150 characters; enlarge it only when requested. A missing directory is unavailable, not a no-match. Do not inspect other OpenCode stores.

## Git unreachable-object recovery

Use only the explicitly named checkout/root set, after confirming that every selected repository and worktree is admitted. Root selection keeps the legacy precedence: positional checkout; direct child checkouts under `PROJECTS_DIR`; `PROJECT_ROOT`; `REPO_ROOT`; then the current Git checkout. The environment roots must be configured for this request and admitted in full; never treat a broad root as permission to inspect its children. If no checkout can be resolved, report not searched. This recovery is read-only: `git fsck` supports `--no-reflogs`, `--unreachable`, and `--no-progress`; inspect candidates with `git show --no-patch` / `git diff-tree`. Never use `--lost-found`, which writes beneath `.git/lost-found`, and never alter refs, reflogs, objects, or worktree state.

Run this snippet with the calling tool's native timeout set to at most 30 seconds, and cap the displayed candidates at 20. The snippet deliberately does not depend on GNU `timeout`, `gtimeout`, Bash arrays, or Bash 4 features. If the calling runtime cannot impose a finite timeout, report not searched. A timeout or reached candidate cap makes coverage partial; an empty result from an incomplete scan does not prove that no additional commit exists.

```bash
HIST_LIMIT=20
shown=0
scan_root() {
  root="$1"
  while IFS= read -r wt; do
    while IFS= read -r oid; do
      git -C "$wt" show --no-patch --format='%H %s' "$oid"
      shown=$((shown + 1))
      if [ "$shown" -ge "$HIST_LIMIT" ]; then return 0; fi
    done < <(git -C "$wt" fsck --no-reflogs --unreachable --no-progress 2>/dev/null | awk '$2 == "commit" { print $3 }')
    if [ "$shown" -ge "$HIST_LIMIT" ]; then return 0; fi
  done < <(git -C "$root" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p')
}

if [ -n "${1:-}" ]; then
  scan_root "$1"
elif [ -n "${PROJECTS_DIR:-}" ]; then
  while IFS= read -r -d '' root; do
    scan_root "$root"
    [ "$shown" -lt "$HIST_LIMIT" ] || break
  done < <(find "$PROJECTS_DIR" -mindepth 1 -maxdepth 1 -type d -print0)
elif [ -n "${PROJECT_ROOT:-}" ]; then
  scan_root "$PROJECT_ROOT"
elif [ -n "${REPO_ROOT:-}" ]; then
  scan_root "$REPO_ROOT"
else
  current="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -z "$current" ]; then
    echo "PROJECT_ROOT not configured: select a checkout path or run from the requested repository" >&2
    exit 2
  fi
  scan_root "$current"
fi
```

## Legacy time filters

The helper does not implement legacy `--recent N` or `--date YYYY-MM` options. Do not forward those options or silently ignore them. Preserve the requested cutoff and apply it only to an admitted source query whose timestamp field and scope are verified. If using a bounded helper sample, timestamps can filter displayed entries but cannot prove a complete time-window search; state partial/unknown coverage when the full declared source scope was not searched. A no-match verdict requires evidence that the admitted scope was read and parsed through the requested cutoff.

## Human-prompt and intervention audits

Only do this analysis when requested. Verify authorship from source context; `role=user` alone is insufficient. Count verified human prompts separately from related follow-up episodes, retain exact event IDs, timestamps, source/runtime, and excerpts within the chosen budget, and treat index hints as inconclusive. Attribute a PR only from an explicit or independently corroborated identifier; otherwise mark it unassigned. Actor and intervention labels are evidence-based judgments, never keyword classifications. Partial or unknown coverage is not zero.
