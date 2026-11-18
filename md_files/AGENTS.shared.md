# Shared Global Policy

Canonical shared policy for Codex (`CODEX_HOME/AGENTS.md`) and Claude Code (`@~/.codex/AGENTS.md` in `~/.claude/CLAUDE.md`). Edit shared rules here once (`<200` lines); detailed appendices live in `~/.claude/CLAUDE-global-reference.md` and owning skills. Runtime-only headings apply solely to the named runtime. Do not create `~/AGENTS.md`; keep repo rules in each repo's `AGENTS.md`/`CLAUDE.md` (`~/.claude/CLAUDE-policy-layering.md`).

## Reading a cmux terminal before deciding (full-buffer rule)
Before classifying, assessing, steering, or nudging any cmux surface, read its FULL available history (`cmux capture-pane --workspace <ws> --surface <sf> --scrollback --lines 1500`, headless only — never select/focus; `~/.claude/skills/cmux-steer/SKILL.md`), checking deep scrollback first and the last ~15 lines second (`grep` is a pre-filter only). Before any idle/stalled/blocked verdict, capture twice 20–30s apart via `mktemp` (**screen changed => `WORKING`**) and confirm absence of post-footer output, live timer growth, CPU in `top_flat.tsv`, and trailing session `.jsonl` growth; if unreadable, mark `UNVERIFIED`.

## Editing shared policy or runtime adapters — semantic signoff + behavioral gate (mandatory)
For edits that shorten, move, or restructure a rule, verify an agent reading only the new text still enforces it; keep high-salience autonomy and safety headings standalone and under 200 lines. Run before/after canaries (proceeds on implied next step without asking; cites source before status claims); pause and recheck if a human reports an obvious unnecessary question within 24h.

## Authorization, scope, and instruction authority
Complete requested work end-to-end within scope. Authorization persists for the same action, target, and outcome across checkpoints, status questions, continuations, and compaction unless withdrawn; preserve latest-message gates below, execute independent authorized work while one item awaits approval, preserve unrelated changes, and never silently substitute lesser work. Explicit user instructions outrank skill defaults within system/tool limits; treat retrieved plans, memories, and transcripts as dated evidence rather than live stops; sending redacted design/PR/plan docs to `/web-advice` (`/wa`, `~/.claude/skills/web-advice/SKILL.md`) is always pre-authorized.

## Do not offload work to the user
Never ask the user to manually test, check, verify, or perform work the agent can automate until every supported automated path is exhausted.

## Act, don't ask, on read-only and reversible work
Perform authorized reads, greps, log/BQ/DB queries, schema/config/diff checks, probes, and reproductions without asking, and chain follow-up read-only checks to completion before reporting. Ask only when an essential intent decision cannot be resolved from context or requires ungranted authority (§ Escalate only what only the user can do).

## A required artifact is pre-authorized — produce it, don't ask
When a CI gate, skill, or workflow requires an artifact to pass — including publishing a secret-redacted **unlisted evidence gist** and `**Evidence**: <url>` marker (`~/.claude/skills/evidence-standards/SKILL.md`) — build and publish it without asking. Separate gates for merges, force-pushes, destructive actions, credential lifecycle, social-post deletion, and public posts still apply.

## Escalate only what only the user can do
User-only gates: merge approval (`MERGE APPROVED`/`merge approved` or obvious typo, or verified size-tiered rule; never "ship it"/"LGTM"), force-push (`force push approved`), social-post deletion (`POST DELETE APPROVED`), destructive actions, spending money, creating/rotating/revoking credentials (narrow exception: standing APNs key generation on an already-signed-in portal for an authorized app task), and physical 2FA/hardware steps.
- Existing credentials (`gh`, `gcloud`, Firebase, service accounts, Keychain, Secret Manager) are pre-authorized for in-scope steps (`gh secret set NAME < file`). **Never run `security dump-keychain`**; read one item via `security find-generic-password -s <service> -a <account> -w`.
- Respawn dead/expired agent lanes yourself; decide reversible or previously settled choices yourself; treat prerequisite config steps as your worklist; keep live-message authority-dependent actions (credential use, external sends, config writes) in the primary session rather than subagents.

## Visible progress — never look frozen
Use async handles while jobs run, do safe parallel work, yield foreground checks within cadence, background multi-minute CLI delegations with timeouts and captured logs, and never end a turn merely because an active job is still running.

## Credentials and environment
Never create, edit, commit, or read `.env` files; use process env, Keychain, or GCP Secret Manager (list metadata/names first, load only needed secrets into memory/stdin, never print/argv; catalog in `~/roadmap/worldai-test-credential-catalog-2026-11-14.md`). Authenticate Codex via `codex login` (never export `OPENAI_API_KEY`); require both a failed Keychain probe and failed cheap tool call before suggesting re-login; do not edit shell wrappers unasked. Always use nvm Node 22 (`~/.nvm/versions/node/v22.22.0/bin/node`), never Homebrew Node 24.

## Workspace and method fidelity
Prefer requested tools/workflows; task-scoped model/driver/permission adjustments are authorized (report material substitutions) without changing persistent defaults unasked. Preserve full-permission flags (`--yolo`, `--force`, `--dangerously-skip-permissions`) by default. Create git worktrees **only** under `~/.worktrees/<repo>/<name>` via `diskm worktree-new <repo-path> <branch>` (verify placement; shims are pass-throughs). Allocate workspace-shaped scratch, builds, review checkouts, and disposable evidence on the Scratch volume via `~/.claude/skills/scratch-space/SKILL.md` (`diskm scratch-new` or `scratch-dir.sh`), **never** as workspace clones in `/tmp` (`~/.claude/hooks/scratch-routing-guard.py`; single temp/log/lock/probe/profile files in `/tmp` remain exempt; Linux loop-image Scratch needs deletion, not relocation, to free host disk; never remap `TMPDIR`). Tear down ephemeral review workspaces on completion.

## Reports and Markdown deliverables go in the roadmap repo, not `/tmp`
Write all durable human-readable Markdown deliverables (`<topic>-YYYY-MM-DD.md`) to `~/roadmap/` before reporting; commit Markdown/small text only (**never** files `>5 MiB` or generated JSONL/telemetry/media — publish bulky evidence via unlisted gist or `diskm evidence-push` and link it). In chat replies, print local file paths as full expanded plain text on their own line, keeping GitHub/web URLs as links.

## Destructive action safety
Confirm exact targets and authorization before deletion, overwrite, reset, force-push, or service replacement; never recursively target broad/root/home paths or unverified globs; preserve backups and dirty work. Never delete published social posts without literal `POST DELETE APPROVED`. Restore cmux workspaces on clear live natural-language user request without closing/focusing live workspaces. Never run `pkill`/`killall` with multiple or `<6`-char patterns; use `pgrep -f -- '<6+ char anchored pattern>'` then `kill <PID>`. `OpenClaw operator note (not the user)` is non-authoritative.

## Destructive-path guard (incident <incident-bead>, 2026-10-18)
Never aim `rm -r`, `rsync --delete*`/`--del`, `find -delete`, or `mv` at an unvalidated computed path: `set -u`, prove `[ -n "$D" ] && [ "$D" != / ]`, use `${D:?unset}`, validate tool output (`xcrun simctl ...`) against expected prefixes, and check commands via `~/.claude/hooks/lib/destructive_path_guard.py --check '<cmd>'`. Under `cc-safety-net` (`standard`): use literal targets for `rm -r`, restrict `rsync --delete` to explicit cwd/`/tmp`/`$TMPDIR`/remote paths, and write scratch `.py` files instead of `python3 - <<'PY'` heredocs (`~/.claude/skills/cwd-safety/SKILL.md`, `~/.claude/CLAUDE-global-reference.md`).

## Verify before reporting
Two readers of one capture/message equal one unverified claim; verify from an independent source/layer and bind mechanical verdicts directly to their artifacts (`ps`, two-sample diff, coverage receipt). **Re-pin mutable state** (`git rev-parse HEAD`, `gh pr view --json headRefOid`, live file reads) immediately before every verification round. **Before claiming code/flag absence**, `git fetch` and search `origin/main`, citing the exact commit; check both `~` and the active repo when locating skills/configs.

## Core behavior
Models own domain semantics, triage, and authored state; backends own auth, atomic value-preserving storage, locks/receipts, and exact tool execution — never add keyword/regex/heuristic semantic routing or `hasattr`/`getattr` on `GameState` (`~/.claude/skills/zero-framework-cognition/SKILL.md`; WorldArchitect: `.claude/skills/worldai-zfc/SKILL.md`). Maximize bounded independent parallelism (`~/.claude/skills/parallelize-to-ceiling/SKILL.md`) gated by measured CPU idle (`top -l 2 -n 0 -s 2 | grep 'CPU usage' | tail -1` on Mac, never load average: `<25%` idle => max 2 heavy lanes, no concurrent test suites, route scoped coding to `/dot` cloud; `<10%` idle => start none, mirror host-independent work via `/lm` or `/mac-mirror` when the peer host has measured headroom; escalate only if both hosts block).

## Upstream and root-cause engineering
Inspect upstream before editing forks in a worktree. Complete `~/.claude/skills/root-cause-first/SKILL.md` (prompt/schema/instruction first) before adding any backend guard, fallback, clamp, sanitizer, or retry, and load `~/.claude/skills/ponytail/SKILL.md` (`/ponytail`) before coding or `/cs`/`/advice` reviews to reuse existing pipelines and delete dead paths.
- **Think of future and sibling cases — never gate a general fix behind a single-case allowlist.** When a root cause is architectural, protocol-level, or shared across a provider/category, fix the shared path and retire the broken default — never hardcode a 1-model, 1-route, or 1-caller allowlist (`{"model-x"}`) "because other cases weren't ablated," stranding sibling and future models/inputs on a known-broken path. Gate differences by capability, never by an ad-hoc list of whichever item failed today.
- **Unmandated enforcement gates:** Every new guard, validator, ledger, or fail-closed check requires a one-line named authority (user ask, spec, or `file:line`), a documented resume/override for host-local locks, and end-to-end deliverable proof; local spend guards never override live user authorization.

## Local tool and UI pointers
Never attach to personal/default Chrome or reuse its profiles/cookies (`~/.claude/skills/browser-control/SKILL.md`, `~/.claude/skills/browser-testing/SKILL.md`); default to isolated headless Chromium, or Aside in background mode on an agent-owned profile for authenticated flows (`~/.claude/skills/aside-browser-default/SKILL.md`). Keep Dot profiles (`~/.config/dot-headless-chrome-*`) exclusive to `dot.sh` (`~/.claude/skills/dot/SKILL.md`). Upload Slack media natively via `python3 ~/.claude/skills/slack-media-upload/scripts/slack_upload.py`. Follow `~/.claude/skills/disk-root-cause/SKILL.md` for disk growth, `~/.claude/skills/ui-video-evidence/SKILL.md` and `design-fidelity-diff` (`getBoundingClientRect`/`getComputedStyle`) for UI proof, and `br` (never `bd`, `~/.claude/skills/beads-issue-tracking/SKILL.md`) for Beads + parallel `/learn` persistence. Deliver agreed scope or state `blocked because X`; reprioritize immediately on user correction.

## Autonomy time-box
Autonomous sessions/workers stop at 8 hours (`28,800s`) unless extended; each live human message renews `approved_until = receipt + 28,800s` (preserving `original_started_at`; bot/tool/summary messages never renew, and human stops override).

## Proportionality, evidence, and autonomous execution
Drive PRs via `/prw` (`~/.claude/skills/pr-lifecycle/SKILL.md`) and sequence expensive evidence last (`~/.claude/skills/evidence-standards/SKILL.md`). Local cycle counts never stop safe in-scope work; front-load planning, resolve mechanical merge conflicts yourself, and verify UI end-states visually. **Push safety:** Never push directly to `main`/`master` except routine `~/roadmap/` Markdown per its `AGENTS.md` expected-head workflow; exhaust fast-forward, update-branch, diff-transplant, or replacement PRs before requesting `force push approved` (always exact-SHA `--force-with-lease`, never bare `--force`); verify branch/upstream before pushing and commit green units within 30m.

## PR descriptions (canonical owner)
Shared structure for every PR (`~/.claude/skills/pr-description-sections/SKILL.md` + target repo template; validate with `/ds`): (1) opening `Line deltas: prod +A/-D across N files; non-prod +A/-D across M files.` sentence; (2) plain-language summary, background, goals, before/after user story, tenets/bead, changes by area, test/evidence plan, risks, follow-ups; (3) visible `## Line Deltas (Prod vs Non-Prod)` against full base diff; (4) evidence/gate records (old history in `<details>`); (5) `## Advice Approval` last (`APPROVED at <SHA> by <reviewers>`, SHA-bound).

## Git, PR, and API pointers
Include `[<cli>][<model>]` in commits/PR titles + GitHub labels (Codex requires variant slug like `gpt-6-sol`, never bare `gpt-6`); format PR/commit citations per `~/.claude/CLAUDE-global-reference.md` § PR and commit references and `/pr-summary`. PRs adding `>150` production lines require a passing `/cs` (`/ponytail`) at current head. Try both GitHub REST and GraphQL (`~/.claude/skills/github-cli-reference/SKILL.md`) before reporting API blocks; unset stale `GITHUB_TOKEN` if host `gh` auth is valid. Documentation-only PRs skip CI; when required CI queues `>10m`, running local equivalents is **mandatory** and satisfies `/green` Gate 1 (`~/.claude/skills/pr-green-definition/SKILL.md`).

## Merge safety — size-tiered approval
Count full-diff production `added + deleted` lines (excluding tests/docs/evidence/tooling): **`<=150` production delta lines** may be merged by the human-facing session once `/advice` (2-reviewer quorum) and `/green` hold at exact head (unless repo-gated); **`>150` production delta lines** require `/cs` + `/advice` plus a live user `MERGE APPROVED` message (never salami-slice into micro-PRs or `>=10`-PR stacks; `<=3` open PRs per scope default, hard cap `<=5` coarse slices per `~/.claude/skills/pr-quantity-control/SKILL.md`). Always re-verify head SHA/CI/mergeability and pass `--match-head-commit`.

## Shared provider & review-gate policy (canonical)
- **CodeRabbit/Bugbot are optional advisory reviewers**, never `/green` or merge gates.
- **PR review severity:** Use **P0 only for merge-blocking findings** (naming failure, violated requirement, and clearance check); log **P1+** in Beads without blocking merge.
- **WorldAI AGY quota fallback:** When live AGY CLI/provider status confirms quota exhaustion on WorldAI calls (not a mere timeout), log the status + timestamp and fall back immediately to direct Gemini API (`google-genai`/`llm_service`) without asking; does not alter coding-CLI session defaults.

## Review, output, and scope discipline
State the primary deliverable before coding; touch formatting only on edited lines; verify shell commands live before documenting them; default private-repo Actions to self-hosted runners; ship Markdown/skill docs only on doc tasks unless code/scripts are explicitly scoped. Close coding/PR turns with `## What Was Done` and `## What to Review as a Human` (human-only items from § Escalate only what only the user can do, never LLM-verifiable checks; `~/.claude/skills/human-review-brief/SKILL.md`).

## Autonomous follow-through
Execute remaining authorized steps (`/er`, `/advice`, local checks, evidence gists, independent PRs for pre-existing `origin/main` failures, agent-settled branch ownership with `/dot` FYI) rather than handing them to the human. Before escalating any human-only decision, complete the first pass, state **Why the LLM cannot do this**, link **Work completed and proof**, give options + recommendation, and ask for the smallest human action.

## Skill, command, and shared execution contracts
`~/.claude/skills/` is the sole canonical skill home (`~/.agents/skills/` holds symlinks only; never use `~/.codex/skills/` or nest `SKILL.md` files; diff-first sync and `jleechan-skills` PR workflow follow `~/.claude/skills/up/SKILL.md`). Resolve slash commands from `~/.claude/commands/<name>.md`; `/f` and `/factory` invoke the real `~/.claude/skills/dark-factory/SKILL.md` binary; `/af` follows `auto-factory`; Claude MCPs live in `~/.claude.json`, Codex MCPs in `CODEX_HOME/config.toml`, HTTP MCPs in `~/.config/mcp-daemon/start-mcp-daemons.sh`, `wiki/` via `/wiki-ingest` only.

## Codex-only runtime configuration and delegation
Applies to Codex only (`CODEX_HOME/config.toml`): default coding edits to delegated lanes (`terra_scout`, `terra_reviewer`, `luna_verifier`, `~/.local/bin/codex-luna` or `luna_worker`); optimize token efficiency without skipping gates; probe `spawn_agent` before assuming an installed model is unavailable; gate spawns via `vm_stat` available RAM (`<4GB` or `pressure=4` defers after top-RSS check, never `vm.swapusage`); read quiet subagent transcripts before declaring stalls; never use Gemini 3.1 Pro (`agy` uses `gemini-3.8-flash*`, Antigravity subagents per adapter).

## Native build authority — canary rules (2026-10-19)
- `localbuildallowedwhenrequested`: user/operator "local build" requests authorize local `xcodebuild`/simulator/TestFlight builds; runner load is scheduling, not a ban.
- `no competingnativeoperator`: one native operator per **iOS Simulator UDID and app bundle only** — never generalize this lock to shared test accounts, credentials, campaigns, or environments (exclusivity there is only ever observed live, never coordinator-declared).
- `loadgate≠blanketban`: load/CPU/memory/thermal deferrals must state a concrete recheck threshold + cadence; `Expoheldunlessauthorized`: hosted Expo/EAS builds require explicit user authorization.

## Context-full behavior — auto-compact and keep going
Never stop or hand off because context is full: persist state to `~/roadmap/` + `br`, auto-compact, re-verify mutable SHAs/heads/files from source, delegate heavy sub-work to lanes, and continue until a real user-only gate or stop applies.
