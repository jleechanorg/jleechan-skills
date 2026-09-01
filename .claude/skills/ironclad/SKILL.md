---
name: ironclad
description: Use when the user invokes /ironclad, asks for ironclad exit criteria, or sets a sparse goal that needs hardening before autonomous work.
---

# Ironclad exit criteria — harden, set, execute

**Provenance of the standard** (mined via /ms + /history, week of 2026-07-05..12):
- User, 2026-07-12 (session 40c1f666): *"whenever i do /goal i want the llm to brainstorm some ironclad exit criteria **better than what i asked for** and then run it"* → became the `~/.claude/hooks/goal-exit-criteria.sh` UserPromptSubmit hook (3–7 criteria, literal condition is the floor).
- User, 2026-07-10 (worldai-2d /goal): *"make ironclad exit criteria and **iterate until the game truly working**"* → ironclad implies an iterate-until-verified loop, not a one-shot checklist.
- Exit-criteria charter (dark-factory `cutover-exit-criteria.md`, R1–R6 + X1–X10; adopted by the spec-design-docs skill): binary, executable, externally anchored; implementer-authored artifacts are corroborating, never sufficient; the verifier **reproduces** rather than inspects; satisfied-via-mock/dry-run = FAIL; default verdict is FAIL.
- Live validation (DK2D mission, 2026-07-12): iterate-until blocked premature closure, and independent verification caught a stale-bundle over-claim.

## Scope and process ceiling

Ironclad strengthens proof that the requested outcome works; it does not broaden the requested product scope. "Stronger than asked" means closing concrete loopholes in verification and failure containment, not adding features, redesigns, deliverables, or process artifacts. Every criterion must trace directly to the stated goal or a demonstrated failure mode.

Use three criteria by default and at most five unless the user explicitly requests more or the task is genuinely high stakes. Use one criteria-setting pass and one independent verification pass. When a check fails, fix that failure and rerun the affected checks; do not restart full planning or review. Follow `~/.claude/CLAUDE.md` section "Delivery over process", including its 30-minute implementation-or-verification limit.

Reuse the active tracker and goal state. Create a new bead, roadmap file, STATE entry, or memory pointer only when the task actually spans sessions, the active workflow requires it, or the user requests it. Tracking is never completion evidence.

## What "ironclad" means (all six required per criterion)

1. **Stronger proof, same scope** — the user's literal condition is the floor for evidence. Close concrete loopholes in satisfying the intended outcome without adding features, deliverables, surfaces, gates, or evidence classes. Record a materially broader idea as an optional follow-up; never promote it into an exit criterion.
2. **Binary** — pass/fail, no "mostly"/"improved"/"should".
3. **Executable** — a stated command or observable check anyone can run verbatim (quote it in the criterion).
4. **Externally anchored** — verified at the layer users experience (real system-of-record: merged PR state, live HTTP response, on-camera DOM, CI conclusion at head SHA) — never implementer logs/telemetry alone.
5. **Anti-gaming** — self-report insufficient; independent reproduction required (different agent/model than the author — adversarial verifier, cross-model review, or the human). Mock/dry-run/dev-mode satisfaction = FAIL. Serving-context matters (dev server ≠ vite preview ≠ backend-served SPA — the wc-1nli/wc-vs19 lesson: validate the SAME bundle/context the claim is about, and prove bundle identity by content hash).
6. **Iterate-until, capped** — the goal stays open until all criteria hold at the same HEAD/state, subject to the termination cap below. Iterate on failing behavior and its checks, not on plans, specs, or unrelated surfaces. A regression reopens the criterion but does not reset the cap.

## Procedure

1. Restate the literal goal in one line.
2. Define three criteria by default (maximum five unless explicitly requested or high stakes). State them as a numbered table: criterion | check command | external anchor | independent verifier.
3. **Set durably when needed**: update the existing goal bead or tracker first. For work that spans sessions, create a goal bead and set Claude Code's builtin `/goal`; keep the builtin condition short. Inside cmux, the model can set it with `cmux identify`, then `cmux send --surface <ref> '/goal <condition>'` and `cmux send-key --surface <ref> enter`. Add a repo-visible goal file only when the active workflow or user requires one.
4. Log to mission STATE only when a sidekick mission is active; add a memory pointer only when the goal spans sessions and no durable pointer already exists.
5. Execute. Route work through the active orchestration model (/sidekick, /swarm lanes) — do not implement directly if the mission delegates.
6. On each claimed completion: run the check commands, cite outputs, get the independent verification, and only then mark the criterion. Default verdict is FAIL.

## Termination and proportionality

An ironclad contract must terminate. Apply all of these limits:

- **Gate-cycle cap:** after two full gate cycles on the same goal or three hours of autonomous work, stop the loop, publish the exact failing criteria and evidence, and surface the scope or authority blocker to the user. Paraphrased self-permission does not extend the cap.
- **Delivery checkpoint:** the shorter 30-minute implementation-or-executable-verification checkpoint in `~/.claude/CLAUDE.md` still applies throughout the task.
- **Evidence sequencing:** run expensive evidence such as real-model calls, browser/video capture, or bundle production once and last, after implementation and blocker triage. Use cheap targeted checks during iteration.
- **Materiality:** a changed HEAD invalidates prior evidence only when the changed files or behavior intersect that evidence. SHA inequality alone is not a reason to rerun every gate.
- **Finding triage:** correctness, security, data-integrity, or requested-behavior defects block completion. Batch their fixes into one new state before rerunning affected evidence. Style, wording, and unrelated improvements become optional follow-ups, not new blockers.
- **Proportionality:** criteria count and evidence depth scale with the requested change's risk. A narrow low-risk change does not receive the maximal gate stack.

## Anti-patterns (ban list — each caught at least once in real missions)

- Criteria satisfied by artifact EXISTENCE ("video file present") instead of artifact CONTENT (all-frames read, >85% single-state = FAIL; region-aware clustering so side-panel text doesn't masquerade as game-world motion).
- "Tests pass" without naming which layer (unit-only proof is insufficient for production behavior).
- Tool-layer proof for end-state claims (`git push` ok ≠ PR mergeable; job "running" ≠ runner online; server "started" ≠ SPA served).
- Criteria the implementer can grade themselves with no reproduction path.
- Validating a DIFFERENT artifact than the claim covers (fresh build vs the stale bundle actually recorded; gate bundle ≠ served bundle).
- Vague quantifiers: "works well", "high quality", "properly handles".
- Expanding proof hardening into new features, architectural redesign, or unrelated deliverables.
- Repeating full planning or review rounds after a narrow blocker is known.
- Producing beads, roadmaps, memory, handoffs, or reports instead of implementing and verifying the requested outcome.

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
