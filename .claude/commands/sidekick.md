---
description: Spawn or respawn a persistent, crash-recoverable Sonnet sidekick — ALWAYS a named in-session Claude Agent-Team teammate (no tmux mode, no codex engine) — for any long-running mission
type: skill
execution_mode: immediate
scope: user
---
# /sidekick — spawn or respawn a Sonnet sidekick (claude team ONLY)

**The sidekick is ALWAYS a named in-process teammate of THIS session's Agent
Team — visible in the user's panel, SendMessage-addressable, `model:
"sonnet"` set explicitly. There is NO tmux mode and NO codex engine; external
tmux sidekicks and `-p` print-mode sidekicks are banned (removed 2026-07-18
by user directive).**

Pattern origin: [Devin Fusion](https://cognition.com/blog/devin-fusion) —
delegation split + cost goal adopted; its dynamic model routing is NOT (the
sidekick model is fixed at spawn). Durability is this skill's own addition.

Load and follow the `sidekick` skill at `~/.claude/skills/sidekick/SKILL.md`
(Skill tool: `sidekick`). **Parallel ceiling:** when fanning out lanes or
subagents, load `/parallel` → `~/.claude/skills/parallelize-to-ceiling/SKILL.md`
first. Works for ANY long-running mission — PR/CI fleets,
research sweeps, migrations, monitoring, ops runbooks, non-repo work — not
just this repo or PRs. Repo-specific rules go in the mission adapter, never
the core protocol.

Usage: `/sidekick [mission...]`

**Instant start:** spawning the teammate is the FIRST action on any
`/sidekick` invocation — write/refresh STATE.md, create/refresh the P1
resumption bead, then
`Agent({name: "sidekick-<mission-slug>", model: "sonnet",
run_in_background: true})` so it appears in the user's own team panel. No
preflight questions.

**Explicit `model` on EVERY spawn** — sidekick and each lane; an omitted
model param inherits the session model (often Fable) and is a policy
violation (audit 2026-07-18, bead $USER-0020).

Durability model: teammates die with the conversation — by design. The
mission survives as STATE.md checkpoints + the P1 resumption bead + frequent
commits, and a fresh session respawns the same named teammate from that
state. Multi-day/overnight missions persist as state on disk, not as a
running process.

- `/sidekick` — respawn: reuse the existing named teammate if the team is
  still live, else respawn from the current project+branch's
  `/tmp/<project>/sidekick/<branch-or-mission>/STATE.md` + resumption bead
  (crash recovery; `/`→`-` in branch names; mission slug for non-repo work).
- `/sidekick audit all launchd jobs and fix drift` — fresh non-PR ops
  mission: write initial STATE.md, spawn the named teammate.
- `/sidekick research LLM eval harnesses for 3 hours, write a report` —
  fresh non-repo research mission using the same teammate pattern.

Behavior contract (details in the skill):
0. **In-session teammate is the ONLY mode.** If Agent Teams fails to form,
   fall back to a named background Agent-tool subagent (same name, same
   explicit `model: "sonnet"`, same STATE.md protocol) and record the
   fallback in STATE.md — never fall back to tmux, never `-p`, never codex
   exec. Route codex work through AO / `/claw` instead.
1. State file first — respawns never overwrite an existing STATE.md.
2. One named teammate owns the mission. Lanes the sidekick fans out CANNOT
   be named teammates (`Agent({name: ...})` called from a teammate, not the
   top-level session, is hard-rejected by the harness — "Teammates cannot
   spawn other teammates, the team roster is flat"); lanes are anonymous
   `general-purpose` subagents with an explicit `model` param instead. If a
   lane's work needs to be user-visible, the sidekick asks the top-level
   session to spawn it directly — only the top-level session can create
   named teammates (confirmed 2026-07-21, see the `sidekick` skill).
3. Commit-often discipline propagated verbatim to every sub-prompt.
4. Never merge / never force-push; milestone reports are captured evidence
   (STATE.md excerpt, git log, PR/commit URL, test output) relayed to the
   user.
5. Proof before claim: verify the teammate appears in the team panel and
   STATE.md's Progress Log advances before saying the sidekick started.
6. **5-minute checkpoint cadence is mandatory** for the sidekick and every
   lane it owns (≤5 min: STATE.md heartbeat, `br update`/`br sync` on the
   resumption bead with a single-writer rule so concurrent lanes never
   clobber the same bead body, safe local commit) — see the `sidekick`
   skill's "5-minute checkpoint cadence" section for the exact mechanics
   and the commit-safety escape hatch (isolated state repo / WIP branch /
   path-scoped `git add`, never `git add -A` on a dirty shared worktree;
   the same escape hatch applies to state files under a gitignored
   `.tmp/`).
