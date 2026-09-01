---
name: ironclad
description: Harden a stated goal into ironclad exit criteria (stronger than asked, binary, executable, externally anchored, anti-gaming, iterate-until), set them durably (bead/goal/STATE/memory), then execute toward them. Use when the user invokes /ironclad, asks for ironclad exit criteria, or sets a sparse goal that needs hardening before autonomous work.
---

# Ironclad exit criteria — harden, set, execute

**Provenance of the standard** (mined via /ms + /history, week of 2026-07-05..12):
- User, 2026-07-12 (session 40c1f666): *"whenever i do /goal i want the llm to brainstorm some ironclad exit criteria **better than what i asked for** and then run it"* → became the `~/.claude/hooks/goal-exit-criteria.sh` UserPromptSubmit hook (3–7 criteria, literal condition is the floor).
- User, 2026-07-10 (worldai-2d /goal): *"make ironclad exit criteria and **iterate until the game truly working**"* → ironclad implies an iterate-until-verified loop, not a one-shot checklist.
- Exit-criteria charter (dark-factory `cutover-exit-criteria.md`, R1–R6 + X1–X10; adopted by the spec-design-docs skill): binary, executable, externally anchored; implementer-authored artifacts are corroborating, never sufficient; the verifier **reproduces** rather than inspects; satisfied-via-mock/dry-run = FAIL; default verdict is FAIL.
- Live validation (DK2D mission, 2026-07-12): the iterate-until rule blocked a premature bead closure on a counting/provenance defect; the independent-verifier rule caught and retracted a stale-bundle sprite over-claim; the stronger-than-asked rule spawned an unrequested persona playthrough that found 3 real defects.

## What "ironclad" means (all six required per criterion)

1. **Stronger than asked — bounded** — the user's literal condition is the FLOOR. Each criterion must close a loophole the literal ask leaves open (ask "how could I technically satisfy the words while betraying the intent?" — then ban that). **Bounding rule (2026-09-01, from the PR #9604/#9640 24h incident):** closing loopholes NEVER adds new deliverables, surfaces, gates, or evidence classes beyond the ask's scope. If a loophole fix would materially expand scope, record it as a proposed follow-up for the operator, not as a criterion.
2. **Binary** — pass/fail, no "mostly"/"improved"/"should".
3. **Executable** — a stated command or observable check anyone can run verbatim (quote it in the criterion).
4. **Externally anchored** — verified at the layer users experience (real system-of-record: merged PR state, live HTTP response, on-camera DOM, CI conclusion at head SHA) — never implementer logs/telemetry alone.
5. **Anti-gaming** — self-report insufficient; independent reproduction required (different agent/model than the author — adversarial verifier, cross-model review, or the human). Mock/dry-run/dev-mode satisfaction = FAIL. Serving-context matters (dev server ≠ vite preview ≠ backend-served SPA — the wc-1nli/wc-vs19 lesson: validate the SAME bundle/context the claim is about, and prove bundle identity by content hash).
6. **Iterate-until, capped** — the goal stays open until ALL criteria hold simultaneously at the same HEAD/state, subject to the Gate-cycle cap in § "Termination and proportionality" below (2 full cycles / 3h time-box — the cap binds this criterion; reading only this list does not exempt you from it); a criterion that regresses reopens the goal but does not reset the cap.

## Procedure

1. Restate the literal goal in one line.
2. Brainstorm 3–7 criteria per the six properties. State them as a numbered table: criterion | check command | external anchor | independent verifier.
3. **Set durably**: `br create "GOAL: <name>" --type task --priority 1` with the full criteria in the description (or `br update` the existing goal bead). Also set Claude Code's builtin `/goal` (Stop-hook enforcement + purple UI indicator); the bead carries the ironclad superset. **The model CAN set the builtin itself when running inside cmux** (proven 2026-07-12): `cmux identify` → caller.surface_ref, then `cmux send --surface <ref> '/goal <condition>'` + `cmux send-key --surface <ref> enter` — types into the session's own composer; the builtin processes it exactly as if the user typed it. Keep the condition short (the UI truncates); single-quote it for the shell. Write a repo-visible goal file (e.g. `roadmap/<mission>-goal-ironclad-<date>.md`) with a live status table when the user should be able to read progress.
4. Log to the mission STATE.md if a sidekick mission is active; add a memory pointer if the goal spans sessions.
5. Execute. Route work through the active orchestration model (/sidekick, /swarm lanes) — do not implement directly if the mission delegates.
6. On each claimed completion: run the check commands, cite outputs, get the independent verification, and only then mark the criterion. Default verdict is FAIL.

## Termination and proportionality (mandatory — PR #9604/#9640 incident, 2026-09-01)

An ironclad contract without a termination rule is a divergent loop: adversarial review finds fixes, fixes move the HEAD, a moved HEAD resets every gate. Every ironclad goal MUST include:

- **Gate-cycle cap**: after 2 full gate cycles on the same goal, or the 3-hour autonomy time-box, STOP — post a status snapshot and escalate the scope question to the operator. Paraphrased self-permission to continue is not authorization.
- **Evidence sequencing**: expensive evidence (real-LLM RED/GREEN, browser/video, bundles) runs ONCE, LAST, after code is complete and all review findings are resolved or deferred. Canonical: `~/.claude/skills/evidence-standards/SKILL.md` § Evidence Sequencing.
- **Materiality on reruns**: "all criteria at one HEAD" binds the FINAL head only. Intermediate iteration uses cheap checks; whether a HEAD move voids evidence is decided by the staleness-tolerance diff test, never by SHA inequality alone.
- **Proportionality**: criteria count stays 3–7 and gate depth scales with the production diff's size/risk. A one-file low-risk change does not get the maximal gate stack.
- **Finding triage**: findings that block correct behavior — correctness, security, or data-integrity defects, regardless of priority label — reset the evidence head; style/nit/doc/wording feedback becomes a tracked follow-up instead. Batch all pending fixes into ONE new SHA before any expensive rerun.

## Anti-patterns (ban list — each caught at least once in real missions)

- Criteria satisfied by artifact EXISTENCE ("video file present") instead of artifact CONTENT (all-frames read, >85% single-state = FAIL; region-aware clustering so side-panel text doesn't masquerade as game-world motion).
- "Tests pass" without naming which layer (unit-only proof is insufficient for production behavior).
- Tool-layer proof for end-state claims (`git push` ok ≠ PR mergeable; job "running" ≠ runner online; server "started" ≠ SPA served).
- Criteria the implementer can grade themselves with no reproduction path.
- Validating a DIFFERENT artifact than the claim covers (fresh build vs the stale bundle actually recorded; gate bundle ≠ served bundle).
- Vague quantifiers: "works well", "high quality", "properly handles".

ZFC note: the harness command is mechanical dispatch; the judgment (which loopholes exist, which criteria close them) is the model's, per the goal-exit-criteria.sh design.

## Verify the structural precondition BEFORE the first grind

Moved here from `~/.claude/CLAUDE.md` on 2026-07-25.

**Rule:** for any ironclad goal with a *sustained-time* criterion ("free ≥ 100 GB sustained 60 min", "p99 latency < 200 ms for 1 h", "error rate < 0.1% for 24 h"), verify the structural precondition holds at goal-met time, not just at tool time. **Do not iterate safe-action reclaim when the rate of renewal exceeds the rate of reclaim.**

Before launching any long-running cleanup / reclaim / sustain loop, ask:

1. Is there an *active producer* (AO auto-spawner, cron job, watch process, log writer) that can refill the resource faster than the planned reclaim rate?
2. If yes, can I structurally stop the producer, or do I have to keep fighting it?
3. If the answer is "keep fighting it", the goal is **unachievable in safe-action time**. Ask the user to pause the producer, accept a partial result, or extend your authority (sudo / kill scope) — and ask within about 5 minutes, not after a long grind.

Measure the *rate*, not the *level*: if the fill rate exceeds the reclaim rate, the goal is unreachable without addressing the producer, no matter how many reclaim passes you run.

**Incident (2026-07-23):** an agent spent 25+ minutes grinding cache reclaims on `jeffreys-macbook-pro` while AO created `/private/tmp/your-project.com` scratch at ~3 GB/min. "Free ≥ 100 GB sustained 60 min" was structurally unreachable until AGY was paused, but the agent kept reclaiming because the user had said "do all the work i asked". A user instruction to be thorough is not a reason to pursue a structurally impossible goal — surface the blocker instead. Memory: `feedback_2026-07-23_ao_respawner_blocks_disk_reclaim.md`.
