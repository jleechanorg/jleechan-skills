---
name: pr-triage-and-next-steps
version: 1.0.0
description: Cross-repo PR draft / ready / conflict / review triage combined with cmux terminal status and a ranked next-steps report. Designed for the "review opens on draft PRs and next steps" pattern that Jeffrey uses. Combines `gh pr list --json`, `cmux tree --all`, and `ao status` into one Slack-thread reply. Trigger phrases - "review opens on draft PRs and next steps", "draft PR inventory", "what PRs are open", "where are we blocked", "cross-repo status", "review the opens", "PR review next steps", "triage drafts", "what is in flight", "show me all open PRs".
---

# PR Triage + Cmux Status + Next Steps

The standing operating mode for "what is going on across the fleet" requests. Verified pattern across the 2026-06-26 (session `20260626_210955_6aa675`) and 2026-07-08 threads. Produces a single Slack-thread reply with three blocks - cross-repo PR table, per-repo draft/conflict/CR drilldown, cmux tree, ranked next steps, 3-question ask.

## Output shape Jeffrey likes (canonical, verified across 2+ threads)

The reply MUST be one Slack message with these blocks in this order:

1. **Top table, cross-repo totals.** Columns are `Repo | Open | Drafts | Ready | Conflicts | CHANGES_REQUESTED | APPROVED`. Total row at the bottom. Markdown links for every repo name pointing to the repo root. No status colors here, the table is dense already.

2. **Repo drill-down, drafts first, then ready-with-blockers.** Pick the repo with the most action (default - `$GITHUB_REPOSITORY`). Drilldown table format is `| # | Title (truncated) | mergeable | notes |`. Markdown-link each PR number to its full URL. Use `MERGEABLE` / `CONFLICT` to color-state mergeable.

3. **Approved cluster** - for any repo with 3+ APPROVED reviews, list them in a small "Ready to merge" table. These are fast wins waiting on `MERGE APPROVED`.

4. **Cmux tree** - daemon status (PID + socket path), selected window/workspace (where the AO inbox lives), then a 2-bullet summary: "Active project surfaces (real work right now)" listing the workspaces whose surface titles map to current PR branches, and "Quiet workspaces" listing the rest by index.

5. **Ranked next steps** - 4 to 6 numbered items, starting with the cheapest highest-value action. End with one explicit "No code-side action this turn" if nothing was touched.

6. **Ranked drive queue, NOT a multi-option menu** - 4-6 numbered items starting with the cheapest highest-value action. End with one explicit "No code-side action this turn" if nothing was touched. **NEVER end with `(a) ... (b) ... (c) ...` choice menus** - that is the SOUL.md `no-pick-one-menus` anti-pattern. The reply paths are the single-word triggers from `roadmap` § E (`GREEN-9-NONPROD`, `AUTO-DRIVE-DRAFTS`, `STUCK-REBASE`, `SPLIT-OVERSIZE`, `BABYSIT-DISABLE`) or the literal token `MERGE APPROVED <BUCKET>` (e.g. `MERGE APPROVED JLEE-5-CLUSTER`, `MERGE APPROVED NONPROD-DRAFTS`). The 3-question ask pattern was verified as a FORBIDDEN stop-halfway pattern at SOUL.md `## COMMIT: no-pick-one-menus`; an early version of this skill encoded it and the operator had to re-run /roadmap to supersede. Do not regress.

7. **Memories used footer** - `🧠 Memories used: [source:…, ids_or_labels:…, effect:…]` per `## COMMIT: ms-on-new-task`.

8. **Pending line** - `Pending — needs your PR review + merge to apply.` when applicable (when code changes were made; not for read-only inventories).

## Data collection, run all four in parallel

```bash
# 1. Cross-repo PR inventory (replaces the broken `--json repository` pattern)
# Run per fleet repo. Iterate `gh repo list jleechanorg --limit 50 --json nameWithOwner`
for repo in $GITHUB_REPOSITORY jleechanorg/jleechanclaw \
            jleechanorg/.github jleechanorg/agent-orchestrator-ts \
            jleechanorg/ai_universe_frontend jleechanorg/browserclaw; do
  gh pr list --author @me --state open --repo "$repo" \
    --json number,title,headRepository,isDraft,createdAt,headRefName,url,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup \
    > "/tmp/open_${repo//\//_}.json" 2>/dev/null
done

# 2. AO daemon status (what worker sessions are in flight)
ao status --json 2>/dev/null | head -200

# 3. Cmux tree (current CLI shape, see `hermes-imports/cmux` skill)
CMUX_SOCKET_PATH=/tmp/cmux-debug-dev-fork.sock cmux tree --all

# 4. Session-search / memory recall, first tool call by SOUL.md mandate
session_search(query="<keywords from user's message>", limit=3)
```

## Tier classification — file-path-authoritative, not title-keywords (added 2026-07-09)

The 2026-07-07 / 2026-07-09 trap, repeated: classifying PRs as "non-prod" by title keywords (`ci:`, `docs:`, `chore(`) is WRONG. A `chore(Dockerfile)` PR can touch `$PROJECT_ROOT/Dockerfile` and be PROD; a `feat(observability): BQ rate-limit telemetry` PR can include `$PROJECT_ROOT/bq_logging.py` and be PROD. Verified 2026-07-09: **51 WA drafts title-keyword-classified as mostly-non-prod → actual 37 PROD + 14 NON-PROD by file-path audit**. The audit also surfaced 1 prod-touching PR (#8066 `fix(LLM): honor user directive to delay world war`) that was title-flavored as `fix(LLM)` (sounds non-prod) but actually edited `$PROJECT_ROOT/` — would have been batch-merged wrongly via `green_merge_nonprod.py` if title-only classification had been used.

**Authoritative recipe (n=51 verified, runtime ~30s):**

```python
import json, subprocess

drafts = subprocess.run(['gh', 'api', 'repos/OWNER/REPO/pulls?state=open&per_page=100',
                         '--jq', '.[] | select(.draft==true) | .number'],
                        capture_output=True, text=True).stdout
draft_nums = [int(x) for x in drafts.strip().split('\n') if x.strip()]

results = []
for n in draft_nums:
    r = subprocess.run(['gh', 'pr', 'view', str(n), '--repo', 'OWNER/REPO',
                        '--json', 'number,title,files,updatedAt,mergeable,isDraft'],
                       capture_output=True, text=True)
    d = json.loads(r.stdout)
    files = [f['path'] for f in d.get('files', [])]
    prod = False
    for fp in files:
        if ((fp.startswith('$PROJECT_ROOT/') and not fp.startswith('$PROJECT_ROOT/tests/')
             and not fp.startswith('$PROJECT_ROOT/test_integration/'))
            or fp.startswith('testing_mcp/') or fp.startswith('testing_ui/')
            or fp.startswith('prompts/') or fp.startswith('$PROJECT_ROOT/frontend_v1/')
            or fp.startswith('$PROJECT_ROOT/frontend_v2/')):
            prod = True
            break
    results.append({'number': n, 'title': d['title'], 'tier': 'PROD' if prod else 'NON-PROD',
                    'files': files, 'mergeable': d.get('mergeable', '?')})

# Buckets for the green-merge candidate list
green_ready   = [r for r in results if r['mergeable'] == 'MERGEABLE' and r['tier'] == 'NON-PROD']
conflicting   = [r for r in results if r['mergeable'] == 'CONFLICTING']
oversize      = [r for r in results if len(r['files']) >= 50]   # split candidates
needs_evidence = [r for r in results if r['mergeable'] == 'MERGEABLE' and r['tier'] == 'PROD']
```

**Apply this recipe BEFORE writing any "draft PR inventory" reply.** Don't trust the title alone. The § B "PR Auto-Merge Candidates" table MUST show post-classification numbers (e.g. "32 candidates from keywords → 14 strict-non-prod → 1 lite-green-ready at this moment"). The honest framing surfaces the user's intuition-vs-policy divergence; the misleading "we tried 32, all blocked" framing hides it. The `roadmap` skill's Pitfalls section already documents this trap; this skill extends it with the executable recipe.

## Pitfalls, verified live

- **`gh pr list --json repository`** - rejects. The field is `headRepository`. Without `--repo OWNER/REPO`, `headRepository` returns blank. Always pass `--repo`. Documented in `agento_report` skill.
- **Empty PR list when running both in one shell** - `gh pr list | python3` interleaves the variable scope; redirect to file in a separate command instead.
- **`cmux list-surfaces`** - does not exist in current CLI. Use `cmux tree --all`. The canonical `cmux` skill already documents this; do not rely on the simplified `hermes-imports/cmux` mirror which may not have the latest CLI-shape section.
- **Socket is dynamic** - `/tmp/cmux.sock` does not exist on this dev build. Always resolve via `lsof -p $(pgrep 'cmux DEV' | head -1) | grep unix` or read `/tmp/cmux-dev-dev-fork-last-socket-path`.
- **Empty reply attempt via `mcp__slack__conversations_add_message`** - if you see `{"error": "text must be a string"}`, the message body contains an unescaped quote / control char. Re-send with a simpler payload or split into multiple messages.
- **`ao status --json` prints notifier-config warnings first** - those lines before the JSON array are expected, grep/head past them.
- **`GH_TOKEN` env var overrides `gh auth switch`** (verified 2026-07-13 in cron status check on PR #8380 / #775) - the default `GH_TOKEN_AGENTF` (or any `GH_TOKEN` set in `~/.bashrc` / launchd-env-wrapper) takes precedence over the active gh account even after `gh auth switch --user jleechan2015`. Symptoms: `gh pr view <N> --repo jleechanorg/<repo>` returns `GraphQL: Could not resolve to a Repository with the name 'jleechanorg/<repo>'` because the wrong account is querying. **Fix:** `unset GH_TOKEN` before `gh auth switch`, then re-run. After switch, verify with `gh auth status` — the active account line should show `jleechan2015` (or whichever target), not the env-var account. Equivalent escape hatch for ad-hoc one-shots: `unset GH_TOKEN; GH_TOKEN=*** gh ...` to inline-override without switching accounts.
- **`gh` honors the macOS Keychain account over env `GITHUB_TOKEN` even WITHOUT `gh auth switch`** (verified 2026-07-14) — distinct from the prior pitfall. When the Keychain has a `gh:github.com` entry for `jleechan2015` and `~/.bashrc` exports a fresh `GITHUB_TOKEN` for a different account, `gh auth status` reports the *keyring* account as active and queries with that account's rate-limit budget. If `jleechan2015`'s budget is exhausted (GraphQL: rate limit), `gh pr list`/`gh pr view` fail even though env `GITHUB_TOKEN` has headroom (`curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit` → `remaining: 4897`). `unset GH_TOKEN` does NOT help — `gh` still picks the keyring account. **Fix:** for read-only GitHub work in this state, skip `gh` entirely and use `curl -sS -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/...`. REST endpoints (`/repos/<O>/<R>/pulls`, `/search/issues`) stay available when GraphQL is rate-limited. Verified same session: `curl /repos/$GITHUB_REPOSITORY/pulls?state=all` returned 15 PRs in <2s while `gh pr list` returned rate-limit error.
- **GraphQL rate-limit fallback to REST** (verified 2026-07-13 same thread) - when `gh pr view` / `gh pr checks` start returning `GraphQL: API rate limit already exceeded for user ID N`, REST endpoints (`gh api ...`) keep working. The mapping is:
  - `gh pr view <N> --repo <R> --json state,mergeStateStatus,reviewDecision,isDraft,mergeable` → `gh api repos/<R>/pulls/<N>` (state, draft, mergeable, mergeable_state)
  - `gh pr checks <N> --repo <R>` → `gh api repos/<R>/commits/<HEAD_SHA>/check-runs` (filter `conclusion != skipped` for the active subset)
  - `gh pr view <N> --json reviewDecision` → `gh api repos/<R>/pulls/<N>/reviews` (last item's `state`, or `NONE` if array empty)
  Always probe the rate limit first when GraphQL errors: `gh api graphql -F query='{ rateLimit { limit remaining resetAt } }'`. If `remaining=0`, switch the rest of the run to REST and note the `resetAt` time in the reply footer so the user knows when `gh pr view`/`gh pr checks` will work again. Don't waste time waiting — REST gives you ~95% of what `gh pr view --json` does.

## Categorization taxonomy

Six buckets. Don't conflate them.

| Bucket | Trigger | Next step implication |
|---|---|---|
| **Draft** | `isDraft: true` | Promote to Ready and request review, or close |
| **Ready (clean)** | `!isDraft && reviewDecision not in (CHANGES_REQUESTED) && mergeable=MERGEABLE` | Already green-light waiting for merge |
| **Conflict** | `mergeable in {CONFLICTING, UNKNOWN}` | `git fetch && git rebase origin/main` round-trip |
| **CHANGES_REQUESTED** | `reviewDecision == CHANGES_REQUESTED` | CR-response commit + rebase |
| **APPROVED** | `reviewDecision == APPROVED && mergeable=MERGEABLE` | `MERGE APPROVED` (or auto for unprotected repos) |
| **No review** | ready, MERGEABLE, no reviewDecision | Awaiting CodeRabbit / cursor review |

A single PR can fall into multiple buckets (e.g. CONFLICT + CHANGES_REQUESTED, which is the worst tier, requires both rebase AND fix commit).

## Slack post format, gotchas

- Slack mrkdwn - pipe `|` in tables is fine, but `|` inside cells should be escaped or rendered as `/`. Code blocks with backticks break tables - separate any cell content with code into a sub-bullet below the row.
- Markdown links - `[#8265](https://github.com/$GITHUB_REPOSITORY/pull/8265)` - no bare `#NNNN` text (per `~/.cursor/rules/pr-hyperlink.mdc`).
- 2,200 chars per Slack message is a soft limit; this kind of report is 8 to 14 KB and fits in one post. If it goes over 4000, split into "Findings" + "Next steps" two messages.
- Color codes like 🟢/🔴/✅/❌ render correctly. Emoji-isolated words like `:green_circle:` (Slack colon notation) do NOT - use the Unicode emoji character literally.

## Field-tested sample (2026-07-09 01:05Z /roadmap supersede)

- 107 cross-repo open (78 WA + 18 jleechanclaw + 1 agent-orchestrator + 10 others)
- **51 WA drafts** — under-counting trap: an earlier reply in the same thread (1m prior) reported 11 drafts; the correct count is 51. The 11-count came from `gh pr list --state open --json` truncating on the agent's first pass; a second pass via `gh api repos/.../pulls?state=open&per_page=100 --jq '[.[] | select(.draft==true)] | length'` returned the full 51. **Always verify draft count via TWO independent paths before posting:** (a) `gh pr list --state open --json number,isDraft --jq '[.[] | select(.isDraft==true)] | length'` and (b) `gh api 'repos/OWNER/REPO/pulls?state=open&per_page=100' --jq '[.[] | select(.draft==true)] | length'`. If they disagree, the higher is correct (REST pagination is more permissive than `gh pr list`).
- 8 strict NON-PROD MERGEABLE drafts (file-path-classified per "Tier classification" section below)
- 6 WA CONFLICTING (5 PROD + 1 NON-PROD), plus 4 STUCK alarms per `roadmap` § 2.5.d
- 5 jleechanclaw APPROVED cluster — `MERGE APPROVED JLEE-5-CLUSTER` literal-token gate
- Cmux — daemon alive, selected workspace `workspace:3 "--- w: fable bulk"`, 28 workspaces
- 0 active AO sessions (`ao session ls` empty across all projects)
- 15 ranked drive items in /roadmap § D — NO multi-option ask, single trigger words only

## Anti-patterns (do NOT)

- Do not **fabricate** AO session statuses - `ao status --json` is the only source. If the daemon hangs, say so.
- Do not post partial reports split across replies - produce one consolidated reply or two ("Findings" / "Next steps") at most.
- Do not ask "want me to drive X?" mid-report. End with the question, then stop.
- Do not auto-merge anything on `$GITHUB_REPOSITORY` - branch protection requires explicit `MERGE APPROVED` from Jeffrey (per `~/.claude/CLAUDE.md` "Merge safety").
- Do not cite `🦺/🧠` emojis as `:emoji_name:` colon codes - use Unicode literals directly.

## Verify cited identifiers before echoing them back

When a user message — or a Slack thread you've been pulled into — cites an identifier of any kind (bead ID, memory file path, commit SHA, branch name, "the fix is in PR #N"), **do not echo it back in your reply without verifying**. The agent's class failure mode is "the user said `rev-g7ov4`, so my reply says `rev-g7ov4`, and now both my reply and any PR description I help write cite a bead that does not exist in any beads DB". Verified 2026-07-21 on PR #8462 ($GITHUB_REPOSITORY): the user's update cited "Bead: rev-g7ov4 (mission)" — `br show rev-g7ov4` returned "Issue not found" and `br search "cold replica"` returned only `rev-8q7xp`. The same false bead ID was already cited in PR #8462's body (`the brief originally referenced rev-zurdo but that ID did not exist in the beads DB — rev-g7ov4 is the actual ID this mission opened`) — meaning the cited bead was wrong at PR-creation time and stayed wrong through 8 head changes.

**One-line check per identifier class, before echoing in any reply or PR description:**

| Identifier class | Fast verification | Citation check |
|---|---|---|
| Bead ID (`rev-xxx` / `bd-xxx`) | `br show <id>` in the relevant repo's beads DB | "Issue not found" → flag in reply, do NOT parrot |
| Memory / feedback file path | `ls <path>` (or `glob` if path is fuzzy) | not found → say so, do NOT pretend it exists |
| Commit SHA (`<id>` / `<short>`) | `git rev-parse <id>` in the relevant repo | not a valid object → flag |
| PR description cite of bead/file | `gh pr view <N> --json body` then re-run the line-above verifications on what the description cites | at minimum verify the bead/cite ones — they're the load-bearing ones reviewers and humans downstream will copy |
| Branch name on a remote | `git ls-remote origin <branch>` | 404 → flag |

**Where to apply this rule (every reply that mentions any of these):**

- PR triage / status reports (this skill's main use case)
- PR descriptions you author or amend
- Slack-thread replies that re-quote another message's identifiers
- Memory entries that paraphrase a prior session's identifiers without re-checking

**Companion rule (already encoded in `.cursor/rules/research-integrity.mdc` for URLs):** "Do not treat search snippets as evidence." Same discipline, broader scope — extend it to "Do not treat user-cited identifiers as fact without verifying in the live store."

**When you find an ID is wrong**, your reply should:
1. Flag the miss-cite explicitly with the correct ID ("`rev-g7ov4` not found in beads DB; closest match is `rev-8q7xp`")
2. Use the verified-correct ID in your reply
3. Mention the miss-cite in the PR / Slack message so the author can fix it in source (the wrong ID often lives in a PR body or design doc that everyone downstream copies)

**Why this matters more than a routine double-check:** the wrong-identifier drift compounds. Once `rev-g7ov4` is in the PR body and the user's update message, every agent that "use[s] /ms and slack search and see what PRs already merged" inherits it. The drift is invisible until someone runs the verification.

## Related skills

- `hermes-imports/cmux` - full cmux CLI shape, socket resolution, multi-app probe
- `hermes-imports/agento_report` - AO-status + per-PR CI/code review check shape (lower-level; this skill extends it for cross-repo + cmux + next steps)
- `roadmap` - different (48h Slack sweep + /nextsteps); this skill is for **on-demand** cross-repo pulls, not recurring sweeps
- `cmux-surface-report-4h` - recurring 4h inventory cron; this skill is **on-demand** for direct user requests
- `hermes-imports/finish-the-job` - drives chosen PRs through green after triage; this skill produces the triage report, that one drives the response