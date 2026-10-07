---
name: cmux-surface-report-4h
version: 1.3.0
description: "Daily 08:00 PT cmux terminal surface inventory + classification. Lists every selected cmux workspace/surface, reads each pane briefly, classifies as Healthy/Risky/Blocked, and posts a per-surface digest (with pinned-first priority, full PR hyperlinks, and smarter 'working on' extraction) to Slack home channel. Runs via launchd plist (LAUNCHD-ONLY since v1.3.0, 2026-07-24). v1.3 changed the cadence from every-4h to a single daily 08:00 tick, renamed the report header from '(4h)' to '(Daily)', and removed the LLM-cron twin."
tags: [cmux, monitoring, launchd, periodic, slack, daily]
category: monitoring
triggers:
  - cmux surface report
  - cmux daily report
  - cmux inventory
  - cmux health digest
  - daily cmux check
  - what is cmux doing
  - cmux status
related_skills:
  - cmux
  - cmux-terminal-review
  - launchd-job-authoring
  - cron
  - slack-messaging
  - skillify
---

## v1.3.0 — cadence flipped to daily 08:00 PT (2026-07-24, user request)

User said "Make this a daily report only at 8am" in Slack thread
`C0AJQ5M0A0Y / p1784891379.012009`. Three changes shipped in one PR:

1. **LaunchAgent schedule reduced to a single `StartCalendarInterval`**
   (Hour=8, Minute=0, TZ=America/Los_Angeles). The previous six-tick
   per-day array (00/04/08/12/16/20 at minute 07) was deleted.
2. **Slack header renamed** from `*cmux Surface Report (4h)*` to
   `*cmux Surface Report (Daily)*`. Same channel
   (`${HERMES_CMUX_4H_CHANNEL:-C0AJQ5M0A0Y}` = `#ai-general`).
3. **LLM-cron twin was never active** (`hermes cron list | grep cmux` = `none`)
   so no disable was needed; the skill doc dropped the historical
   `cron/jobs.json` "LLM-cron sibling" framing. Single source of truth
   = the LaunchAgent.

Verified PR: [jleechanorg/jleechanclaw#799](https://github.com/jleechanorg/jleechanclaw/pull/799)
heads `83f3891564` (1st commit) + `026b0237c6` (2nd commit, "stale 4h
cron comment fix"). Local rendered LaunchAgent at
`~/Library/LaunchAgents/com.$USER.cmux-surface-report-4h.plist` was
edited, lint-checked, `bootout`/`bootstrap`-reloaded, and re-verified with
`launchctl print` (`Hour=8, Minute=0`) in the SAME session as the source
PR — see pitfall §"Live rendered LaunchAgent reload gate" below.

The historical `cmux-surface-report-4h` label and filename are kept
intentionally (label, plist, script, tests) to avoid migration risk on a
shell-only change. The cadence and report header — the only user-visible
surfaces — were changed.

## Cadence-change pitfall — Live rendered LaunchAgent reload gate (2026-07-24)

When you change the schedule in the source plist **and** the rendered
LaunchAgent is already loaded, the source PR alone is INVISIBLE to the
running daemon. The daemon keeps firing on the schedule it loaded into
its cache when the LaunchAgent was first registered. Verified sequence:

```bash
PLIST="$HOME/Library/LaunchAgents/com.$USER.cmux-surface-report-4h.plist"
LABEL="com.$USER.cmux-surface-report-4h"
DOMAIN="gui/$(id -u)"

# 1. Edit the rendered plist (NOT just the .template — that lives in the
#    git repo; the LaunchAgent under ~/Library/LaunchAgents is the live file)
#    Re-render from the new template:
sed "s|@HOME@|$HOME|g; s|@HERMES_EXTRA_PATH@||g" \
  launchd/com.$USER.cmux-surface-report-4h.plist.template > "$PLIST"

# 2. plutil -lint MUST pass before reload
plutil -lint "$PLIST"

# 3. bootout → bootstrap to force the new schedule into launchd's cache.
#    bootout can fail silently if the job isn't running — that's OK, ignore.
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl enable "$DOMAIN/$LABEL"

# 4. VERIFY — this is the only proof the change is live. If you skip
#    this you ship a source PR that disagrees with the running daemon.
launchctl print "$DOMAIN/$LABEL" | egrep '"Hour"|"Minute"|state ='
plutil -extract StartCalendarInterval json -o - "$PLIST"
```

Both proof blocks must show **the new schedule** (`Hour=8 Minute=0`).
If `launchctl print` still shows the old array, the `bootout` was a
silent no-op because the job wasn't registered yet — `launchctl bootstrap`
re-registers; verify again. Bug-ref: Slack thread
`C0AJQ5M0A0Y / p1784891379.012009` (2026-07-24).

## Cadence-change pitfall — Codex Spark usage-limit retry (2026-07-24)

The first AO spawn for this cadence change was `--harness codex` and hit
its account usage limit before editing anything. The worker reported
*"You've hit your usage limit for GPT-5.3-Codex-Spark. Switch to another
model now, or try again at Jul 29th, 2026 4:22 PM."* and the session
went idle with no commits.

**Correct retry recipe (no time spent debugging the Codex harness):**

1. `ao session kill <old-id>` (clean up the orphan)
2. Re-`ao spawn` with `--harness agy --model gemini-3.5-flash-high`
   (mid-tier — verified 2026-07-24). `--harness codex` was the
   failure mode; switching to antigravity/agy's Gemini path bypassed it.
3. Preserve the verbatim user task and memory context in `/tmp/...AO-TASK-BRIEF.md`
   so the second worker has the same brief without re-deriving it.
4. After the worker pushes, audit PR #N before posting completion.

Anti-pattern: spending 10+ minutes debugging `codex --full-auto` /
`codex` plugin args, or upgrading Codex quota, when the user explicitly
asked for a one-line schedule change. Mid-tier is correct for "config /
launchd / docs" work; do not escalate to a top-tier model for that.

## Cadence-change pitfall — update everything or ship dead code (2026-07-24)

Green Gate FAILed on the first push because `scripts/cmux-surface-report-4h.sh`
still contained a "Cron registration" example that said
`hermes cron create "every 4h"`. CodeRabbit called it out and Green Gate
gated on it (CR approval = "FAIL"). Fix in the same PR — when you
change the schedule, grep for the old cadence in EVERY file under the
project (script comments, skill body, resolver triggers, tests, fixtures)
and update them in the same commit, not in follow-ups.

Grep that catches this class:

```bash
rg -nE 'every 4h|4h cadence|StartCalendarInterval|ThrottleInterval.*14400' \
   scripts/ skills/ launchd/ tests/
```

## ⚠️ Submit Discipline (MANDATORY — read this before every cmux steer)

`cmux send` does **NOT** press Enter. This is the #1 recurring cmux failure mode
(verified 2026-07-16: user explicitly flagged "you always forget to send" after the
fable iOS pivot bootstrap). The **4-step ritual** below is a hard contract for every
send to a cmux surface. Skip ANY step and the message sits in the input buffer
without ever reaching the agent.

### The 4-step ritual

```bash
# STEP 1 — Type the text. OK response only proves socket acceptance, NOT submission.
cmux send --workspace workspace:N --surface surface:M "your message"

# STEP 2 — Press Enter. send does NOT auto-press Enter.
cmux send-key --workspace workspace:N --surface surface:M enter

# STEP 3 — Wait 5-15 seconds for the agent to start processing.
sleep 8

# STEP 4 — Verify with churning label (THE ONLY definitive proof).
cmux capture-pane --workspace workspace:N --surface surface:M --lines 25
# Look for one of:
#   - "Working (Xs • esc to interrupt)"
#   - "Forming… (Xs · thinking)"
#   - "Precipitating… (Xs · ↓ tokens)"
#   - "Brewed / Churned / Cooked for Xm"
# If you see ANY active churning label → SUBMITTED.
# If the text is still sitting at the ❯ prompt → NOT submitted, repeat step 2.
# If "Stopped" / "Done" / nothing → no churn, investigate.
```

### ⚠️ Output Contract — typed text + terminal response (MANDATORY)

Every reply that reports a `cmux send` action MUST include, in the same reply:

1. **The exact text that was typed** — verbatim copy of the string passed to `cmux send`.
2. **The cmux terminal response** — verbatim transcript of what `cmux capture-pane` /
   `cmux read-screen` returned AFTER the `cmux send-key enter` settle window
   (typically 5-15s). Specifically, the agent's first action after absorption.
3. **Submission status** — explicit verdict: "submitted (churning label X)",
   "not submitted (text still at ❯ prompt)", or "blocked (no churn, retried N times)".

**Treat as not working until we see a response.** A reply that does NOT include
both the typed text AND a terminal response is invalid evidence that the
steer landed. The operator cannot distinguish a successful send from a failed
send that left text in the input buffer.

Canonical contract + echo-back template: `~/.hermes/skills/cmux/references/output-contract-mandatory.md`.

### ⚠️ LLM-Provenance Caveat (MANDATORY footer)

Every reply that quotes cmux output, terminal text, or agent actions produced
by another LLM (the worker agent OR the assistant's own synthesis of agent
output) MUST end with this verbatim footer:

> *This was generated from another LLM and not the actual user, so feel free
> to push back if you disagree and we can discuss.*

This skill is read-only (it captures cmux surface state via `cmux tree` and
posts to Slack); the caveat MUST appear in every Slack post this skill emits
that quotes surface content / agent activity.

Full caveat rules + scope: `~/.hermes/skills/cmux/references/output-contract-mandatory.md` § "LLM-Provenance Caveat".

### Echo-back proof (MANDATORY)

Every cmux steering action MUST be followed by an **echo-back proof** in the same
turn or the immediate next turn to your operator (Slack thread, terminal reply,
or whichever channel triggered the steer):

> ◀ sent to surface:55 (LEFT/claudec) at <HH:MM:SS PT> — 4-step ritual complete;
> churning label "Forming… 9s · ↓ 4.9k tokens" confirmed via capture-pane.

**Banned** (these are the failure modes the user keeps flagging):
- "I sent the message" (no Enter proof)
- "The agent should have received it" (no churning label)
- `cmux send` with no follow-up `cmux send-key enter`
- Sending to a surface that hasn't been focused (the global focus may be on a
  different workspace; use the raw RPC `surface.focus` if needed)

### Worktree-pointer strategy for long briefs

For task briefs >200 chars (e.g. orchestrating iOS app pivot, multi-PR review),
do NOT paste the full text into the input. Write the brief to a file in the
agent's cwd (e.g. `.cmux-<task>-brief.md`) and send a 1-2 line pointer. This
avoids the autocompleter contamination pitfall where shell-style tokens inside
long text trigger tab completion mid-stream.

### Canonical reference

Full recipe + edge cases + the 2026-06-25 worked example live at:
`~/.hermes/skills/cmux/references/send-submit-proof-2026-06-25.md`

This rule was added 2026-07-16 after the fable iOS pivot bootstrap surfaced
"you always forget to send" / "make sure you press submit and the work starts
on the cmux input" (Slack ts 1784185650.528089). Apply it uniformly to every
cmux-touching skill.

# cmux-surface-report-4h

**Every-4h cmux terminal inventory + Slack digest.** This skill composes the production-grade `cmux-surface-report-4h.sh` (already live in `~/.hermes/scripts/`, scheduled via launchd plist at `~/Library/LaunchAgents/com.$USER.cmux-surface-report-4h.plist` AND an LLM-cron twin in `~/.hermes/cron/jobs.json`) with the contracts: SKILL.md, tests, RESOLVER trigger entry, and the deploy-pipeline sync.

## v1.2 improvements (2026-06-24, per Jeffrey's request)

Four quality-of-life improvements landed in one turn:

1. **Pinned workspaces float to the top.** A new file
   `~/.config/cmux/pinned-workspaces.txt` lets Jeffrey pin specific
   workspaces by exact ref (`workspace:14`) or by case-insensitive
   name fragment (`agento`, `latency`). Pinned surfaces always appear
   first in the report (priority 1, regardless of class), marked with
   📌. Empty lines and `#` comments are allowed.

2. **Full PR hyperlinks** in the `next:` line. Bare `#N` references
   are now emitted as `[#N](https://github.com/jleechanorg/<repo>/pull/N)`
   markdown hyperlinks per `.cursor/rules/pr-hyperlink.mdc`. The repo
   is auto-detected from the screen text. Falls back to the
   `$CMUX_REPORT_GH_REPO` env var (default: `$GITHUB_REPOSITORY`)
   when no repo is mentioned. Three real bugs were caught and fixed
   during this pass: the doubled-owner pattern
   `github.com/jleechanorg/jleechanorg/<repo>/pull/N` (Slack renders
   BOTH the visible hyperlink text AND the raw URL), the bare-`#N`
   branch falsely linking to the default repo when the screen
   references an unrelated repo, and a template bug that doubled
   the `jleechanorg/` prefix when `default_repo` already contained it.

3. **Smarter "working on" extractor.** Instead of the first matching
   line, the extractor now scores each line by (PR-mention = +3,
   activity-keyword = +2, later-in-screen = fractional) and picks the
   best. This means a deep log line like `※ recap: Shipped P4
   prompt-substitution audit to dark-factory via PR #99 (merged at
   d68d52b)…` wins over a header line that happens to say "Running".

4. **Skillify pass.** Tests, RESOLVER entry, and SKILL.md contract
   refreshed to cover the new behavior. Test file grew from 31 to 51
   passing cases.

## Why this skill exists

Three drift patterns were observed before this skillification (2026-06-20 to 2026-06-22):

1. **Parser regression producing 72 bogus "blocked" entries** — the 2026-06-20 08:29 tick double-counted surfaces because awk couldn't parse Unicode box-drawing chars. Replaced with Python parser + sanity cap (TOTAL > 100 aborts post).
2. **launchd job had no Slack token** — the wrapper script (`-wrapper.sh`) was added to source `launchd-env-wrapper.sh` so `HERMES_SLACK_BOT_TOKEN` reaches the script. Without the wrapper, every tick silently no-ops.
3. **Two duplicate scheduler entries** (one launchd, one LLM-cron) — both posting to the same channel. Verified harmless because both call the same script; documented for audit clarity.

## Contract

**When this skill fires, ONE end-state is provably true:**

| End-state | Proof artifact |
|---|---|
| **Slack post landed in `#ai-general`** | One message per tick: `*cmux Surface Report (Daily)* :emoji: {healthy\|risky\|blocked}\nWorkspaces: N surfaces checked \| Healthy: H \| Risky: R \| Blocked: B\n_Tick: ISO8601 \| Socket: <name>_` |
| **Tick skipped cleanly** | Log line `No live cmux socket — skipping this tick.` at `~/.hermes/logs/cmux-surface-report/YYYY-MM-DDTHH.log` |
| **Tick aborted due to parser regression** | Log line `TOTAL=N exceeds sanity cap (100) — aborting to avoid bogus post.` (exits 1, no Slack post) |

**NOT acceptable end-states:**

- ❌ Tick runs but posts to wrong channel (the SOUL.md `slack-channel-routing-policy` COMMIT pins `#ai-general` (`C0AJQ5M0A0Y`) for all periodic traffic — never `#all-$USER-ai`).
- ❌ Tick runs with `HERMES_SLACK_BOT_TOKEN` unset and silently exits (the wrapper enforces this — if launchd-env-wrapper.sh is missing, the wrapper FATALs, never silently no-ops).
- ❌ Tick runs with > 100 surfaces (capped and aborted, NOT posted).

## Phases (every 4h cadence)

### Phase 0 — Wrapper sources launchd env

The wrapper (`cmux-surface-report-4h-wrapper.sh`) is the only entry point. It:

1. Sets `LABEL=com.$USER.cmux-surface-report-4h` and `LOG_TAG=cmux-surface-report-4h`.
2. Sources `~/.hermes/scripts/launchd-env-wrapper.sh` (which extracts `HERMES_SLACK_BOT_TOKEN`, `HOME`, `PATH` from `~/.bashrc`).
3. Execs the actual `cmux-surface-report-4h.sh` via `bash -c "source ...; exec ..."` (the wrapper exec's its arg).

**Why a wrapper:** launchd does NOT source `~/.bashrc`. Without the wrapper, the report script has no Slack token and silently exits 0 with `No Slack token available — skipping post.` in the log.

### Phase 1 — Socket resolution

The script reads `/tmp/cmux-last-socket-path` first (cmux's own pointer file), then falls back to `ls -1 /tmp/cmux*.sock /private/tmp/cmux*.sock`. If neither yields a live socket, the tick exits 0 cleanly (no Slack post).

### Phase 2 — Tree parsing

Tries `cmux tree --window window:1` first (works on dev build `cmux DEV may-18.app`), then falls back to `cmux tree --all`. Both wrapped in `timeout 8`. Parses the tree with Python (NOT awk — Unicode box-drawing chars break awk). Emits a list of `(workspace, surface)` pairs where surface is `[selected]`.

### Phase 3 — Per-surface classification (loop)

For each pair, calls `cmux read-screen --workspace workspace:N --surface surface:N --lines 25`, filters cmux's own `Error:` lines, and classifies into one of three buckets:

| Bucket | Regex on filtered screen | Example signal |
|---|---|---|
| **BLOCKED** | `Traceback\|panic:\|FATAL EXCEPTION\|segmentation fault` | Python traceback visible |
| **RISKY** | `confirm?\|Do you want to\|approve?\|permission to` | Awaiting user approval |
| **HEALTHY** | `Running\|processing\|generating\|building\|claude--\|Working on\|thinking` | Active work |
| **HEALTHY** (idle) | (none of above) | Quiet/idle terminal |

Each classification logs to the per-tick log file. Sanity cap: TOTAL > 100 aborts the post (catches parser regressions before alarming the channel).

### Phase 4 — Slack post (jq + curl)

Builds a one-line `*cmux Surface Report (4h)* :emoji: {label}` digest with up to 3 blocked + 3 risky details, posted to `${HERMES_CMUX_4H_CHANNEL:-C0AJQ5M0A0Y}` via direct `chat.postMessage`. `unfurl_links:false` to keep the message tight.

## Files

| Path | Purpose |
|---|---|
| `~/.hermes/scripts/cmux-surface-report-4h.sh` | Main script (8288 bytes, 220 lines) |
| `~/.hermes/scripts/cmux-surface-report-4h-wrapper.sh` | launchd wrapper (1280 bytes, sources launchd-env-wrapper.sh) |
| `~/.hermes/launchd/com.$USER.cmux-surface-report-4h.plist.template` | launchd plist template (with `@HOME@` placeholders) — single `StartCalendarInterval` Hour=8 Minute=0 since v1.3.0 |
| `~/Library/LaunchAgents/com.$USER.cmux-surface-report-4h.plist` | Rendered plist (substituted `$HOME`). The live file; reload via bootout/bootstrap after editing |
| `~/.hermes_prod/skills/cmux-surface-report-4h/SKILL.md` | This file (prod mirror) |
| `~/.hermes_prod/skills/cmux-surface-report-4h/tests/test-classify.sh` | Unit tests for the classifier regexes + sanity cap |
| `~/.hermes/skills/RESOLVER.md` | Trigger entry: `cmux surface report`, `cmux daily report`, etc. |
| `~/.hermes/logs/cmux-surface-report/YYYY-MM-DDTHH.log` | Per-tick logs (one file per hour) |
| `~/Library/Logs/com.$USER.cmux-surface-report-4h.log` | launchd-level log (wrapper output) |

**Removed in v1.3.0:** the `~/.hermes/cron/jobs.json` LLM-cron twin
(`hermes:cmux-surface-report-4h`, job id `086ee863b35a`). It was never
active (`hermes cron list | grep cmux` = `none`), so this is a docs-only
removal.

## Loader / auto-fire contract

This skill is registered in `~/.hermes_prod/skills/RESOLVER.md` and `~/.hermes/skills/RESOLVER.md` with trigger phrases: `cmux surface report`, `cmux 4h report`, `cmux inventory`, `cmux health digest`, `4h cmux check`, `what is cmux doing`, `cmux status`. The skill fires when a user asks about cmux state from the LLM session; the launchd plist fires independently of the LLM session on its 4h cadence.

## Deploy sync awareness

This skill is part of the **hermes-deploy-pipeline** deploy set. Stage 4.5 of `scripts/deploy.sh` only syncs `POLICY_FILES=(CLAUDE.md SOUL.md TOOLS.md HEARTBEAT.md)`. So:

1. The script lives in `~/.hermes/scripts/` (staging repo = git-tracked). Commit + push to origin main.
2. The plist template lives in `~/.hermes/launchd/` (staging repo = git-tracked). Commit + push.
3. The rendered plist lives in `~/Library/LaunchAgents/` (NOT git-tracked). Re-render via `sed` from the template after deploy.
4. The cron entry lives in `~/.hermes/cron/jobs.json` (staging repo). After deploy, mirror to `~/.hermes_prod/cron/jobs.json` (gateway live state).

**The cmux entry exists in BOTH staging and prod cron** (job id `086ee863b35a`), so deploy.sh Stage 4.5 is sufficient — no custom rsync needed for the cron entry.

## Related skills — load order when this fires

1. `cmux` (always — the underlying terminal multiplexer that this skill inventories)
2. `launchd-job-authoring` (only when adjusting the plist template)
3. `cron` (only when adjusting the LLM-cron twin)
4. `slack-messaging` (only when adjusting the post format)

## Reference

- `references/cadence-flip-2026-07-24.md` — verbatim transcript of the every-4h → daily 08:00 PT cadence change, including the live rendered LaunchAgent reload recipe, the Codex Spark usage-limit retry pivot to `--harness agy`, the cron-duplicate audit, and the Green Gate FAIL→fix loop on PR #799.

## Worked example — 2026-06-22 healthy tick

```
*cmux Surface Report (4h)* :white_check_mark: healthy
Workspaces: 4 surfaces checked | Healthy: 4 | Risky: 0 | Blocked: 0
_Tick: 2026-06-22T20:07:14Z | Socket: cmux-9b80e9da.sock_
```

(Live output from the 2026-06-22 20:07 PT tick; verified in `#ai-general` channel.)