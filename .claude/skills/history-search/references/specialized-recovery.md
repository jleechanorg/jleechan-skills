# Specialized history recovery (on demand)

Begin with [the sparse workflow](../../conversation-history-sparse/SKILL.md) for source admission, provenance, excerpt budgets, and coverage language. These procedures do not grant access to sources or repositories. Keep each source's results distinct from supported-helper coverage.

Use this reference only when the user explicitly requests one of these procedures, or when admitted supported-source results are insufficient and the procedure is relevant. Before running any query, verify that the required path is admitted. If the needed bounded route or tool is unavailable, report that source as unavailable/not searched; do not widen access or silently skip a requested filter.

## Claude per-session deep retrieval

The normal helper CLI accepts a larger `--limit`, but its Claude search still returns at most three matches per JSONL file. When a user requests more results from an admitted Claude history scope, call the same installed helper's `search_claude` function with explicit result, per-file, and excerpt limits. It still scans at most the 10 most relevant project directories; do not treat the returned bounded sample as exhaustive. Resolve `HISTORY_HELPER` and admit its reachable Claude projects as described in [the sparse workflow](../../conversation-history-sparse/SKILL.md).

~~~bash
HIST_LIMIT=20
HIST_PER_FILE=20
HIST_CHARS=500
python3 -c 'import importlib.util, json, sys; helper, query, cwd, limit, per_file, chars = sys.argv[1:]; spec = importlib.util.spec_from_file_location("history_search", helper); module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); rows = module.search_claude(query=query, cwd=cwd, limit=int(limit), max_per_file=int(per_file), max_chars=int(chars)); print(json.dumps([row.to_dict() for row in rows], ensure_ascii=False, indent=2))' "$HISTORY_HELPER" "$HIST_QUERY" "$PWD" "$HIST_LIMIT" "$HIST_PER_FILE" "$HIST_CHARS"
~~~

Keep the query as a positional value, retain the exact returned file path and timestamps, and report the chosen bounds. Larger requested previews may raise HIST_CHARS; larger requested samples may raise both result limits, while the 10-project-directory scan bound remains.

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
partial=0
command_failed=0
scan_worktree() {
  wt="$1"
  while IFS= read -r oid; do
    if [ "$oid" = "__HIST_FSCK_FAILED__" ]; then
      echo "[fsck:$wt] command failed; coverage partial" >&2
      partial=1
      command_failed=1
      return 0
    fi
    if description="$(git -C "$wt" show --no-patch --format='%H %s' "$oid" 2>/dev/null)"; then
      printf '%s\n' "$description"
      shown=$((shown + 1))
    else
      echo "[show:$wt] could not read candidate $oid; coverage partial" >&2
      partial=1
      command_failed=1
    fi
    if [ "$shown" -ge "$HIST_LIMIT" ]; then
      echo "Candidate display cap reached; coverage partial" >&2
      partial=1
      return 0
    fi
  done < <(
    set -o pipefail
    git -C "$wt" fsck --no-reflogs --unreachable --no-progress 2>/dev/null | awk '$2 == "commit" { print $3 }'
    fsck_status=$?
    set +o pipefail
    if [ "$fsck_status" -ne 0 ]; then printf '%s\n' "__HIST_FSCK_FAILED__"; fi
  )
}
scan_root() {
  root="$1"
  if ! git -C "$root" rev-parse --git-dir >/dev/null 2>&1; then
    echo "[git:$root] unavailable: not an admitted Git checkout" >&2
    partial=1
    command_failed=1
    return 0
  fi
  worktree_output="$(git -C "$root" worktree list --porcelain 2>/dev/null)"
  worktree_status=$?
  if [ "$worktree_status" -ne 0 ]; then
    echo "[git:$root] worktree list failed; coverage partial" >&2
    partial=1
    command_failed=1
    return 0
  fi
  while IFS= read -r wt; do
    case "$wt" in
      "worktree "*) wt=${wt#worktree }; scan_worktree "$wt" ;;
    esac
    if [ "$shown" -ge "$HIST_LIMIT" ]; then return 0; fi
  done <<EOF
$worktree_output
EOF
}

if [ -n "${1:-}" ]; then
  scan_root "$1"
elif [ -n "${PROJECTS_DIR:-}" ]; then
  while IFS= read -r -d '' root; do
    if [ "$root" = "__HIST_FIND_FAILED__" ]; then
      echo "find failed under PROJECTS_DIR; coverage partial" >&2
      partial=1
      command_failed=1
      continue
    fi
    scan_root "$root"
    [ "$shown" -lt "$HIST_LIMIT" ] || break
  done < <(
    find "$PROJECTS_DIR" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null
    find_status=$?
    if [ "$find_status" -ne 0 ]; then printf '%s\0' "__HIST_FIND_FAILED__"; fi
  )
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
if [ "$partial" -ne 0 ]; then
  echo "Git recovery coverage is partial or unavailable; do not claim exhaustive results." >&2
fi
if [ "$command_failed" -ne 0 ]; then
  exit 2
fi
```

## Legacy time filters

The helper does not implement legacy `--recent N` or `--date YYYY-MM` options. Do not forward those options or silently ignore them. Preserve the requested cutoff and apply it only to an admitted source query whose timestamp field and scope are verified. If using a bounded helper sample, timestamps can filter displayed entries but cannot prove a complete time-window search; state partial/unknown coverage when the full declared source scope was not searched. A no-match verdict requires evidence that the admitted scope was read and parsed through the requested cutoff.

## Human-prompt and intervention audits

Only do this analysis when requested. Verify authorship from source context; `role=user` alone is insufficient. Count verified human prompts separately from related follow-up episodes, retain exact event IDs, timestamps, source/runtime, and excerpts within the chosen budget, and treat index hints as inconclusive. Attribute a PR only from an explicit or independently corroborated identifier; otherwise mark it unassigned. Actor and intervention labels are evidence-based judgments, never keyword classifications. Partial or unknown coverage is not zero.
