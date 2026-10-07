# Bug Hunt Daily — Fail-Closed Fix (2026-07-22)

## What broke

`scripts/bug-hunt-daily.sh` in `jleechanorg/jleechanclaw` posted the
Slack report for `20260722_162942` as:

```
*Daily Bug Hunt Report - 20260722_162942*
*Repos scanned:* jleechanorg/jleechanclaw $GITHUB_REPOSITORY jleechanorg/ai_universe jleechanorg/beads
*Period:* Last 2 days
*Agents deployed:* claude codex minimax
*PRs reviewed (0):*
*Results:*
- PRs reviewed: 0
- Bugs found: 0
- Agent failures: 3/3
:warning: ALL bug hunt agents failed to run. 0 bugs recorded — this is NOT a clean sweep.
```

The truthful state was: **0 PRs reviewed because `gh pr list` hit a
GraphQL rate limit, so no workers should have been spawned at all.**

## Root causes (three independent anti-patterns in one script)

1. **Discovery failures were coerced into empty state** —
   `get_merged_prs()` did
   `gh pr list ... | jq ... 2>/dev/null || echo "[]"`. A `gh` rate limit
   (verified: `GraphQL: API rate limit already exceeded for user ID
   13840161`) was silently coerced into `[]`, propagating as "0 PRs
   merged" to the worker prompts.

2. **Workers were spawned against empty input** — the script iterated
   `claude / codex / minimax` even when `PRS_JSON="[]"`, producing three
   empty tasks.

3. **Prose output counted as agent failure** — workers received
   `Analyze these merged PRs for bugs: []`, returned prose like
   `"No merged PRs were provided to review..."`, the
   `perl ... /```json\n?(.*?)\n?```/s` extractor produced empty files,
   the empty-file branch counted each as an agent failure, and the
   fail-closed `ALL_AGENTS_FAILED` summary posted `:warning: ALL bug
   hunt agents failed to run`.

Bonus finding: all three `.err` files showed `OpenAI Codex v0.144.5 /
model: gpt-5.3-codex-spark` — so the "Agents deployed: claude codex
minimax" header was fabricating three distinct agents when there was
really one Codex instance (the historical `hermes agent --agent <name>`
subcommand no longer exists in this Hermes profile, but the script was
falling back to a single Codex path).

## Recipe — what the fix looks like

State grid the script must track:

| Upstream `gh` rc | Input list | Worker outcomes | Slack summary line |
|---|---|---|---|
| non-zero | n/a | n/a | `:warning: discovery failed — gh returned <err>; 0 PRs reviewed; see <err file>` |
| 0 | empty (`[]`) | (skip spawn) | `0 PRs reviewed in window — clean, no findings` |
| 0 | non-empty | all valid `[]` JSON | `N PRs reviewed, 0 bugs` (no failure warning) |
| 0 | non-empty | N/M produced invalid/empty output | `N PRs reviewed, 0 bugs; :warning: M/N agent failures — see <err files>` |
| 0 | non-empty | all valid JSON with findings | normal bug count + `@hermes Please fix these` |

Concrete code changes:

```bash
# BEFORE — collapses rate limit into "0 PRs"
get_merged_prs() {
    gh pr list ... | jq --arg since "$since_date" '[...]' 2>/dev/null || echo "[]"
}

# AFTER — capture gh rc, write to discovery err file, branch on rc
get_merged_prs() {
    local out rc
    out=$(gh pr list --repo "$repo" --state merged --limit 100 \
          --json number,title,url,mergedAt 2>"${DISCOVERY_ERR}.gh")
    rc=$?
    if [[ $rc -ne 0 ]]; then
        echo "DISCOVERY_FAILED: gh exit $rc for $repo" >> "$DISCOVERY_ERR"
        echo "[]"
        return $rc
    fi
    echo "$out" | jq --arg since "$since_date" '[.[] | select(.mergedAt >= $since) | . + {repo: $repo}]'
}
```

```bash
# BEFORE — spawn loop always runs, regardless of input size
for AGENT in "${AGENTS[@]}"; do
    [ "$HERMES_AGENT_AVAILABLE" -ne 1 ] && { write_empty_findings; continue; }
    (hermes agent --agent "$OCLAW_AGENT" "$HERMES_MESSAGE_FLAG" "$TASK_PROMPT" ...)
done

# AFTER — branch on discovery rc + empty input BEFORE spawn loop
if [[ "$DISCOVERY_RC" -ne 0 ]]; then
    log_warn "discovery failed; skipping worker spawn"
    # mark each worker output as discovery-error so the summary is truthful
    for AGENT in "${AGENTS[@]}"; do
        echo '{"_status":"discovery_failed"}' > "${OUT}_${AGENT}.json"
    done
elif [[ "$PR_COUNT" -eq 0 ]]; then
    log_info "0 PRs to review — skipping worker spawn"
    for AGENT in "${AGENTS[@]}"; do
        printf '[]\n' > "${OUT}_${AGENT}.json"
    done
else
    # existing spawn loop
    ...
fi
```

```bash
# BEFORE — empty file = counted as agent failure
if [ ! -s "$OUTPUT_FILE" ]; then
    AGENT_FAILURES=$((AGENT_FAILURES + 1))
    continue
fi

# AFTER — empty file is valid iff input was empty + worker succeeded
if [ ! -s "$OUTPUT_FILE" ]; then
    if [[ "$DISCOVERY_RC" -ne 0 ]]; then
        log_info "$AGENT — discovery failed; not an agent failure"
    elif [[ "$PR_COUNT" -eq 0 ]]; then
        log_info "$AGENT — no input; not an agent failure"
    else
        AGENT_FAILURES=$((AGENT_FAILURES + 1))
    fi
    continue
fi
```

Worker prompt template — add the defensive clause:

```
Bug Hunt Task for $AGENT:

Analyze these merged PRs for bugs:
$PRS_JSON

If the PR list above is empty (literal `[]`), your ONLY valid response
is a JSON array with no elements wrapped in a single markdown code fence:

```json
[]
```

Do NOT return prose. Do NOT explain why you have nothing to review.
The empty array is the canonical "no findings" shape.
```

## Tests the fix PR must add (jleechanclaw session `jleechanclaw-13`)

- `test_bug_hunt_discovery_rate_limit.py` — monkeypatch `gh` to exit
  non-zero, assert `ALL_AGENTS_FAILED != 1` and the report header says
  "discovery failed" not "agent failures: 3/3".
- `test_bug_hunt_empty_input.py` — monkeypatch `gh` to return `[]`,
  assert no workers spawned, output files contain `[]`, summary line is
  "0 PRs reviewed" not "agent failures: 3/3".
- `test_bug_hunt_prose_output.py` — write prose to an output file,
  assert it counts as agent failure (state c), not as 0 findings.
- `test_bug_hunt_worker_routing.py` — assert that the
  `Agents deployed:` line reflects the actual worker model identity
  (e.g. one Codex path → "codex (×3, identical)"), not three fabricated
  labels.

## Key principle — count states, not strings

A scheduled script that aggregates N workers must end with one of four
honest summaries:

1. discovery failed → `:warning:` discovery path, **not** `:warning:`
   agent path
2. empty input → clean "0 PRs" line
3. partial failure → `:warning:` for the failing subset only
4. all-green → no `:warning:`, just the count

The 2026-07-22 bug-hunt report had the **worst possible shape**:
state 1 (discovery failed) was rendered as state 4 with a warning
attached — looks like real work was attempted and failed, when in fact
no work was attempted at all. The Slack message would have been
correct (and silent) if the script had just bailed on the `gh` failure
before spawning anything.