---
name: swarm
description: Orchestrate multi-agent swarms (ultracode Workflow fan-outs + Agent-team lanes) with adversarial verification, /innov, /advice, and a sidekick durability layer for crash-recoverable runs
---

# /swarm — Multi-Agent Swarm Orchestration Playbook

`/swarm <goal> [--engine workflow|team] [--shape retro|review|solutions|innov|triage] [--sidekick [model]]`

Run a goal as a **swarm**: a deterministic Workflow-tool fan-out (ultracode) or a named Agent-team of interactive lanes, with adversarial verification baked in.

For automatic review of a Codex-origin PR, the PR driver's shared review-dispatch
budget governs reviewer, verifier and advice fan-out in this workflow, including
delegated runtimes. Start only assignments reserved by the driver; if the budget
or authority is unclear, stop automatic reviewer dispatch and ask the driver.
Do not claim an independent review that did not run. Direct user requests for a
specific review, required external gates and non-PR swarm work retain their rules.

- **Parallel ceiling (load first):** `/parallel` → `~/.claude/skills/parallelize-to-ceiling/SKILL.md` sizes shards/workers/lanes to the workload's real resource bound before fan-out. Rule 14 adds utilization/orchestration on top; it does not replace the ceiling skill.
- **The sidekick wrap is mandatory regardless of `--engine`.** `--engine` only picks the fan-out mechanism (Workflow tool vs agent-team lanes), never a way to skip the sidekick; `--sidekick [model]` only overrides its model.

## Quick reference / defaults

| Axis | Default |
|------|---------|
| Engine | Workflow tool (ultracode). Agent teams only for interactive lanes needing mid-flight steering. |
| `--shape` | `retro` \| `review` \| `solutions` \| `innov` \| `triage` — see Canonical phase shapes |
| Durability | ALL swarm work runs INSIDE a sidekick — no inline exception |
| Verification | 3-lens refute-by-default, ≥2/3 to survive; audit dead-verifier false kills (rules 2-3) |
| Models | HARD INVARIANT: explicit `model` on every `Agent()`/`agent()` spawn (rule 1) |
| Output | narrative under `${ROADMAP_DIR:-$HOME/roadmap}/`; unique `/tmp` capture dirs; authorized evidence publication (rules 6-7) |
| Close-out | recipe step 6 (rules 10-12) |

## Examples

```text
/swarm design retrospective for last month --shape retro                      # Collect→Verify→Synthesize→Plan
/swarm code quality audit of src/ --shape review                              # Review→Verify→Innovate→Docs
/swarm one smartest addition per design doc in docs/plans/<dir> --shape innov  # Innovate→Challenge
/swarm fix CI health then drive all open PRs to green --sidekick fable        # crash-recoverable overnight fleet drive
```

**Domain-general by design.** Nothing here is coding-specific: the same shapes (mine → adversarially verify → synthesize → gate) run market research, incident retros, literature reviews, ops audits, planning exercises, content pipelines. Substitute freely: "repo" → any durable shared destination (repo docs, a roadmap repo, wiki, gist); "PR" → whatever review surface the artifact ships to. The invariants that must survive substitution: refute-by-default verification against primary sources, disjoint writer outputs, commit-early durability, false-empty detection, a whole-artifact publishability gate, and cross-model cold review (rule 12).

## Engine selection

| Engine | When | Mechanics |
|--------|------|-----------|
| **Workflow tool (ultracode)** — DEFAULT | Heavy analysis/verification fan-outs: mining, review, audit, design hardening | `agent()/parallel()/pipeline()` script; visible in /workflows; resumable via `resumeFromRunId` |
| **Agent teams** | Interactive lanes needing mid-flight steering or shared task claims | Top-level session creates named teammates (`lane1-history`, `lane4-code` style); the sidekick fans out anonymous subagents only. TaskCreate/TaskUpdate claims + SendMessage; shutdown_request when a lane completes. |
| **Sidekick** — ALWAYS ON | Durable state for ALL swarm work | See Sidekick durability layer. |

"Ultracode" = the Workflow tool, never /team-claude teammates (user corrected this twice).

## Stall watchdog — TUI swarms stall alive on quota modals

The invoking session AND every teammate lane stall SIMULTANEOUSLY on the per-account session-limit modal (`/rate-limit-options`), which never auto-dismisses after the quota window resets. Liveness+progress monitors miss it (process alive, no events). Detect it per Transcript-proof liveness below — STATE.md staleness is a trigger to READ THE TRANSCRIPT, never a stall verdict — and recover per its item 6.

## Transcript-proof liveness (mandatory, user directive 2026-08-30)

File mtimes, STATE.md heartbeat gaps, and roster status strings CANNOT distinguish a hang from a long synchronous tool call (all gave false stall alarms). The ONLY valid liveness/progress evidence is the agent's transcript, and every operator status update MUST quote it:

1. **Locate** (sort by mtime): subagents/teammates → `~/.claude*/projects/<project-slug>/<session-id>/subagents/agent-<id>.jsonl` (teammates `agent-a<name>-<hash>.jsonl`); Workflow journals → `.../<session-id>/workflows/*.json`; background Bash → `${TMPDIR:-/tmp}/claude-*/<project>/<session>/tasks/<task-id>.output` (the glob covers macOS `/private/tmp` and Linux `/tmp`).
2. **Parse, don't tail blindly**: extract the last few `tool_use` / `tool_result` / `text` blocks from each line's `message.content[]`; print timestamp + tool name + truncated input/output.
3. **Redact before quoting** (snippets land in retained logs; mirror `.claude/skills/sidekick/SKILL.md` § "Redact before quoting"): allowlist safe fields (tool name, exit code, byte count, elapsed ms, path basename); mask `KEY=VAL` (≥16-char `VAL`) / `.env` assignments, `://user:pass@host` / `://token@host` credentials, ≥24-char base64/hex runs (bearer/JWT/HMAC), and `--token` / `--api-key` / `Authorization:` values as `***`. Keep the filter minimal: hide only secrets, never *what* the agent is doing.
4. **Quote verbatim**: every status update carries 1-3 redacted, timestamped CALL/RESULT/TEXT lines PER ACTIVE AGENT — not a paraphrase, not "still running".
5. **Stall verdict**: stalled only when the TRANSCRIPT shows no new events across two consecutive checks AND no live OS process (`ps`) backs its last dispatched command. Zero file-diff growth or a stale STATE.md alone is NEVER a stall (a full-suite test run shows nothing for minutes while healthy). **Third branch — stalled-with-modal**: a live tool child in `ps`/`pgrep` (cursor/codex/`claude`) + zero transcript events for two consecutive checks + a known blocked-state marker (`cursor.com/docs/bugbot`, `Rate limit reached`, `quota`, `pro quota`) in the latest stdout or window title. All three must hold — an additional branch, not a relaxation.
6. **Recovery** (only after a transcript-confirmed or stalled-with-modal verdict): ping once, then take over or respawn per the recovery discipline; for a modal stall, dismiss the modal in the parent session and have the lead re-task idle lanes via SendMessage.

## Sidekick durability layer ([Devin Fusion](https://cognition.com/blog/devin-fusion) sidekick pattern)

The sidekick (`~/.claude/skills/sidekick/SKILL.md`, `/sidekick`; its § "The one and only mode", § "Banned patterns") is ONE named in-process teammate of the INVOKING session's Agent Team. The roster is flat, so the top-level session creates every named, panel-visible lane (including ones the sidekick requests); sidekick fan-outs are anonymous. External tmux, codex-engine, and `-p` sidekicks are banned (user directive 2026-07-18). Durability = STATE.md + a P1 resumption bead + commit-often, not process persistence.

- **Main session**: writes/updates `STATE.md`, creates TaskList lanes, spawns the sidekick, relays milestone messages. Nothing load-bearing stays only in conversation context.
- **Sidekick**: reads STATE.md on start (never redoes logged steps), claims tasks, fans out anonymous cost-routed sub-agents when needed, appends to Progress Log + rewrites Next Actions after EVERY step, commits+pushes after every green unit (≤30 min uncommitted), and propagates the commit-often instruction verbatim into every sub-agent prompt.
- **Branch-scoped STATE.md (mandatory)**: each mission gets its OWN `$CLAUDE_STATE_DIR/<project-slug>/sidekick/<branch-name>/STATE.md` (`CLAUDE_STATE_DIR` env, default `~/roadmap`; `<project-slug>` = repo name per the sidekick skill's derivation; `/`→`-` in branch names; mission slug for cross-branch missions, recipe step 1.5). Parallel runs never share a state file (real case 2026-07: one sidekick clobbered another's plan via the shared `## Next Actions` heading). For a legacy shared `.../sidekick/STATE.md` (or pre-migration `/tmp/<project-slug>/sidekick/STATE.md`): migrate only YOUR mission's sections, leave a one-line pointer, treat the rest as read-only.
- **5-minute checkpoint cadence (MANDATORY for the sidekick AND every lane)**: every ≤5 min (1) append a timestamped heartbeat + phase to STATE.md, (2) update the P1 bead body then `br sync` (no `--append` in `br` v0.2.16: `br show <bead-id> --json`, concatenate, `br update <bead-id> --notes "<combined text>"`; `br sync` alone only syncs DB↔JSONL), (3) make a local state commit — a crash loses ≤5 min. Drive it with a background timer/loop or CronCreate; a chat-only status print is NOT a checkpoint.
- **Operator status cadence (MANDATORY, user directive 2026-07-29)**: the MAIN SESSION posts an in-conversation status update every ~5 min while a mission is active, scheduled mechanically at mission start (`CronCreate` `*/5 * * * *`, session-only). Each update: what changed, proven-working vs not (evidence-backed), each lane's activity (transcript snippets), blockers; ping any lane silent 10+ min (after verifying a transcript stall) and say so. Status-only — never start new work from one. Cancel when the mission ends or the operator stops it.
- **Commit-safety**: if the worktree carries unrelated staged/modified work (another actor's diff, a staged deletion), NEVER `git commit`/`git add -A` there — commit state in an isolated `git init` repo (`.tmp/<mission>-state-repo/`) or a WIP branch via `git add -- <state paths>`; gitignored `.tmp/` state needs the isolated repo (or `-f`).
- **Crash recovery / durability boundary**: the sidekick dies with the invoking conversation, by design; `/sidekick [model]` in any fresh session respawns it from STATE.md/bead (one spawn, zero re-derivation). Survives: STATE.md + bead + pushed commits. Does not: same-session `resumeFromRunId` journals, and `/tmp` state across reboots or cleanup.
- **Model**: sonnet by default (explicit `model` param mandatory); `--sidekick fable` is explicit user approval for a fable sidekick (orchestration/diagnosis only, token-economy block required); its sub-agents are always sonnet/haiku. Codex-engine sidekicks are banned — route codex work through AO / `/claw`.

### Quota-out handoff (MANDATORY) — any coding agent must be able to resume

Quota can run out any moment: at mission start AND every checkpoint, persist tasks/specs/goals/wave-plans in **agent-agnostic** form (no Claude-specific tool references; plain commands + file paths + PR URLs):
1. **Primary: one P1 `br` mission bead** (contents per Bead runbook below), updated at the STATE.md cadence, with a single writer per bead (no concurrent-lane clobber). Any CLI (codex, cursor, gemini) can `br search <mission>` and resume.
2. **Fallback when br is unavailable**: plain STATE.md + HANDOFF.md under `$CLAUDE_STATE_DIR/<project-slug>/sidekick/<branch>/`; `/tmp/` only if `CLAUDE_STATE_DIR` is unset AND `~/roadmap` is missing.
3. **Durable artifacts** another agent needs (datasets, ledgers, specs): commit + push to the working branch — /tmp dies with the host, git does not.

### Bead runbook — cross-session recovery beyond /tmp

STATE.md under `CLAUDE_STATE_DIR` survives reboots; legacy `/tmp/...` state does not. The bead is the host-independent recovery pointer; create/update it at mission start with: session id + repo/branch, task list with statuses, wave plan, blocking items, script scratchpad paths, live workflow runIds, output-dir + doc-numbering state ("docs go to `docs/plans/<retro>/pr-retro/` numbered from 05"), pointers to STATE.md + memory files, and the literal next 3 commands to run. A fresh session with no `/tmp` file left must be able to `br search <mission-keyword>` and resume from the bead body ALONE. Close it only when the close-out (provenance comment + `/learn`) actually lands.

## Canonical phase shapes (all proven 2026-07)

| Swarm | Phases | Shape |
|-------|--------|-------|
| design-retro | Collect → Verify → Synthesize → Plan | 6 themed miners (history, memory/beads, git churn, codebase, CI, PR logs) → 3-lens adversarial verify per candidate → 1 synthesis → 1 plan-doc writer per confirmed finding (42 agents, 7/10 confirmed) |
| solutions-hardening | Attack → Redesign | N attackers try to break each plan doc → redesigners fold surviving attacks back in (28 agents) |
| pr-retro | Collect → Verify → Solutions | miners over a pre-built dataset JSON (zero live gh calls in agents) → verify → doc per confirmed finding (70 agents) |
| code-quality | Review → Verify → Innovate → Docs | rubric×module-cluster pairs (standards + thermo lenses) → dedup → verify → innovation per problem class → doc per class |
| innov | Innovate → Challenge | one "smartest addition" per finding → adversarial challenge kills weak ideas |
| fleet-triage | single fan-out | one triage agent per PR/lane, structured verdicts (19 agents) |

## Resource admission gate

Before fan-out or CLI delegation, apply the measured CPU/RAM/host-selection gate in [parallelize-to-ceiling](../parallelize-to-ceiling/SKILL.md), subject to current shared policy. Static swap utilization and load average do not establish saturation; attribute pressure to live processes and move eligible work to a suitable host instead of a blanket stop. A resource probe does not authorize killing or restarting another lane. Multi-minute delegates run asynchronously with bounded attempts and captured output.

## Hard rules (each one cost a failure to learn)

1. **Cost-route every spawn explicitly — verify with a grep, not a memory check.** A spawn with no `model` silently inherits the session model. Route `haiku` for mechanical merge/cluster/ls stages, pollers, monitors; `sonnet` for miners, verifiers, fix lanes, doc writers; top tier / main loop only for final synthesis or adversarial judgment with a stated reason. **Before launching any script, run `grep -n "agent(" <script>`** and confirm every match has an explicit `model:` or is the deliberate final-synthesis call (eyeballing misses calls inside a loop/helper). If routing is threaded indirectly (a helper wraps `agent()`), log and confirm the resolved model of each stage's first agent at runtime. Audit each fan-out: if every lane runs the session model, routing was skipped. **Codex parent / `codex exec` / AO:** set `gpt-6-luna` explicitly for research/history/scan/review/mechanical tasks; `gpt-6.1-sol` ONLY when Luna has demonstrably failed (state the failure); 5.6 models forbidden; `reasoning_effort: medium` by default, `high` only for adversarial merge-readiness passes. (Real cases: 2026-07-07 unrouted mechanical stages ran on the premium parent model for weeks; 2026-07-14 10 Fable-inherited spawns; 2026-07-31 7× `/history`+`/harness` reruns on `gpt-6-sol`/`high` = 1.1B tokens.)
2. **Adversarial verify, refute-by-default.** Every candidate finding faces ≥3 independent lenses (e.g. evidence / design / severity) prompted to REFUTE; survive only on ≥2/3 non-refuted. Dedup vs a `seen` set, not vs confirmed.
3. **Audit verifier-death false kills — and detect false-empty completions.** A dead verifier (rate limit, API error) is NOT a refutation; re-verify findings it "killed". **A run returning 0 confirmed findings is a VOID, not a verdict, if `failures[]` shows mass agent death** (every `rejected[].why` reads `DEAD_VERIFIER`/`verifier died`, or failures dominated by `Server is temporarily limiting requests`). 0 findings + healthy agents = real "nothing here"; 0 findings + mass 429/error failures = the stage never ran — re-run it, don't ship or record the empty result. (Real cases 2026-07-07: `pr-retro-gapfill` and `code-quality` Verify stages fully died, falsely zeroing 5 and 20 real findings.)
4. **Rate-limit resilience — concurrency is aggregate, not per-workflow.** Provider 429s kill whole fan-outs, triggered by **total agents in flight across ALL concurrently-running swarms on the account** (2026-07-07: two workflows hit 429 together at ~75 combined). (a) Don't launch a fan-out while another large workflow is mid-fan-out — serialize big stages across sibling swarms. (b) On mass 429: stop, start a ~20-min background cool-down (`sleep 1200` run_in_background or `ScheduleWakeup`), then probe with a **sibling-workflow-as-canary** — a tiny throwaway 1-agent workflow (not "the smallest affected workflow"); relaunch/resume the real workflow(s) only after it succeeds. (c) While cooling down, keep any other running lane to ≤4 concurrent sub-agents. (d) **Stagger — bursts kill, ramps don't.** 429 storms coincided with INSTANT N-wide `parallel()` cold starts (16-60 wide); `pipeline()` ramps and serial work were never throttled. Chunk thunk arrays into batches of ~8 with a few seconds between batches; treat ~16 simultaneous cold starts as the survived ceiling, not a target; never start two workflows' fan-out stages within the same minute.
5. **Resume semantics.** Persist scripts to the session scratchpad (`cp` from the returned Script file path). To resume: TaskStop the run, edit only NOT-yet-completed `agent()` calls (touching a completed call's prompt/opts invalidates its cache), relaunch with `{scriptPath, resumeFromRunId}`. Journals are same-session only — after a crash, re-run fresh from the persisted script; cross-session/cross-reboot recovery needs the P1 bead (Bead runbook).
6. **Disjoint outputs per lane.** Each narrative writer gets an explicit file under `${ROADMAP_DIR:-$HOME/roadmap}/`; each capture/dataset lane its own `mktemp` directory under `/tmp`. Parallel workflows never share a mutable file.
7. **Persist completed units.** One integration owner stages exact authorized files, commits and pushes green units using the owning repository's workflow; concurrent writers do not share an index. Publish durable evidence through the evidence owner, and verify the published artifact and final commit. Never commit raw captures or temporary datasets into a code repository or leave durable findings only in `/tmp`.
8. **Pre-build datasets in the main loop.** Miners read a static dataset JSON (e.g. `prs-last-month.json` built once via gh) instead of making live API calls — deterministic, cheap, rate-limit-proof.
9. **Heartbeats + time-box, cadence scaled to what you're waiting for.** ~270s wakeups suit tight external polling (CI, deploys); poll long multi-agent fan-outs on a 1200-1800s cadence (270s there just burns cache misses). Obey the eight-hour autonomy time-box (user-scope rule) regardless of cadence.
10. **Finish with /advice.** The final package gets an /advice pass (two independent full-coverage CLI votes, normally Codex and Opus; /research is nonvoting) before the closing PR comment; then /learn.
11. **Publishability gate — mandatory final stage, after ALL writer lanes, before the PR is called done.** Verification attacks *candidate findings*, not the *rendered docs*, so run one final small gate over the ENTIRE docset: (a) **redaction sweep** — `rg 'file:///Users|/Users/[a-z]+|ghp_|gho_|x-access-token|serviceAccountKey'` over every published doc, replacing hits with generic placeholders; (b) **cross-doc consistency** — summary-doc numbers diffed against per-finding source docs, disagreements block; (c) **freshness re-baseline** — present-tense claims re-checked at the PR's current head SHA, historical evidence marked "at base `<sha>`"; (d) **supersession markers** — one authoritative doc per finding, superseded drafts banner-point to it; (e) **policy lens** — recommendations checked against repo-specific hard law (e.g. ZFC file boundaries, credential-discipline, regex-approval bans); (f) **recipe validity** — every copyable command/acceptance check states the CORRECT expected outcome (a negative test asserts red, not green); (g) **mechanical hygiene** — `git diff --check` clean. Planning-scope (a workflow stage + checklist), not production code. (Real case: 2026-07-06 design-retro docset, ~180 agents, had all these classes in "confirmed" docs — `docs/design-retro-2026-06-adversarial-gaps.md`.)
12. **Cross-model cold review — MANDATORY, not "when available," for any code-behavior or merge-readiness claim.** A same-model swarm shares one set of blind spots. **Before any "ready to merge" / "bug is fixed" / "evidence PASS" claim is reported (not only after a docset gate), dispatch at least one DIFFERENT model family as a genuinely adversarial reviewer** — codex CLI (`codex exec --dangerously-bypass-approvals-and-sandbox`), gemini CLI, cursor-agent, whatever is installed (`/advice` and `/secondo` suffice only for lighter-weight decisions). Prompt it to (a) reproduce each defect class by executing code, not reading it, (b) check scope creep beyond the PR's claim, (c) check whether evidence proves causation or only correlation. **Independently reproduce its most concrete finding yourself** before accepting the rest (a failing spot-check means re-verify everything). Never skip it because "the swarm already reviewed it" or "we're in a hurry". (Real cases: 2026-07-06 codex found 6 defect classes in a docset ~180 Claude agents passed; 2026-07-10 a same-model /er + /advice pass signed off a "fixed" bug in which one executing codex pass found 5 blockers.)
13. **CI-triggering fan-outs have a SEPARATE capacity ceiling — self-hosted runner/host capacity, not agent concurrency (rule 4).** Subagents that run `gh pr update-branch`, push, or otherwise trigger CI can overwhelm a fixed-size runner fleet even from a small, throttled fan-out (one action → 5-30+ jobs). Before launching, check the target system's current capacity/queue depth and batch the trigger (~15-20 at a time with pauses), even when N is a trivial agent fan-out. (Real case 2026-07-07: a 68-PR `gh pr update-branch` haiku sweep triggered 26+ simultaneous jobs on a 16-runner host and hard-rebooted it.)
14. **Max-parallelization sweep — a blocked gate blocks only its dependents, never sibling work (2026-07-13).** Size with `/parallel` (`parallelize-to-ceiling`) first; this rule is orchestration only. Under-utilization is a failure equal to collision (real case: 5 disjoint prep items idled ~an hour behind one fix). (a) **Standing re-scan**: at EVERY touchpoint (lane report, steer, heartbeat, user ping) re-scan the backlog (`br ready`, open beads, triage tables, STATE next-actions) for work file-disjoint from active writers — continuously, not just at spawn. (b) **Gate scope discipline**: when a verdict blocks an artifact, enumerate exactly which items depend on it; everything else stays dispatchable (no planning-horizon freeze). Prep the gated artifact will CONSUME (harness hardening, ledgers, docs, citations) is the highest-value parallel work. (c) **Utilization metric in STATE**: log `lanes-active / items-dispatchable` at each touchpoint; if dispatchable > active two touchpoints running, spawn lanes (steerable/long-lived) or an ultracode Workflow fan-out (bounded one-shot tasks, explicit `model:`). Foreign/concurrent writers narrow the DISJOINT set — they never justify dispatching nothing.

## Execution recipe

0. **Prompt visible start:** state the deliverable, resolve task context, and pass the Resource admission gate; then promptly start supported in-session lanes with disjoint ownership and a durable mission record. A first-minute visibility target never bypasses admission or requires an unavailable runtime tool.
1. **Recall context first**: `/history <goal keywords>` + `/ms <goal keywords>` — find prior swarms, datasets, and findings before spawning anything else. Session JSONLs may live under `~/.claude-wa/projects/` (not only `~/.claude/projects/`).
1.5. **Sidekick wrap (mandatory)**: write/refresh STATE.md, then spawn or reuse the sidekick via `/sidekick` (lanes from step 0 do the work; the sidekick keeps STATE.md + bead). STATE.md path: on a feature branch use `<branch>`; on `main`/no branch derive the mission slug with the sidekick skill's OWN rule over the full goal text (first 4–6 significant words, lowercased, kebab-case, ~40 char cap) — never a `--shape`-specific variant, so a later bare `/sidekick` recovery recomputes the SAME slug. ALWAYS `ls` the computed STATE_DIR first: existing STATE.md → reuse/respawn that sidekick; missing → fresh spawn. Never let two derivations of one goal spawn two concurrent sidekicks owning one OUTDIR.
2. **Scope lanes** and check independence (disjoint files/OUTDIRs).
2.5. **Continuous utilization check** (rule 14): at every later touchpoint re-scan, log lanes-active/items-dispatchable, and size any new fan-out per `/parallel` before launch.
3. **Author the Workflow script(s)**: meta with named phases, schemas for structured outputs, explicit models, single-file write permission per doc agent.
3.5. **Cost-route gate (mandatory, before launch)**: the rule 1 `grep -n "agent(" <script>` check; fix any bare `agent()` call — never launch on a "looks fine" read.
4. **Launch in parallel** (independent lanes in one message), copy scripts to scratchpad, record runIds in tasks (TaskCreate per lane).
5. **On completion per lane**: commit+push artifacts, audit false kills (rule 3), mark task complete.
5.5. **Cross-model adversarial pass (mandatory, rule 12)** for any lane whose deliverable is a merge-readiness/bug-fixed/evidence-PASS claim on real code.
6. **Close**: publishability gate (rule 11) → /advice pass → PR comment with provenance (runIds, agent counts, token spend) → /learn.
