# /wish skill — specification (2026-11-04)

## Outcome

A user types `/wish <idea>`, `/w <idea>`, or `/wq <idea>` and the agent takes the
idea all the way to PRs: it sizes the task, brainstorms, writes a no-code spec
(with UI mocks when the change is user-facing), plans, builds test-first, and
lands every PR through `/prw`. Small wishes get a small spec and one PR; work that
takes days gets an `/ironclad` contract set as the session goal (`/cmux-goal`), a
`/plan-micro` bead plan, a `/timeline`, and parallel lanes. `/wq` asks no
questions; `/wish` and `/w` ask at most one batched round for decisions that are
genuinely the user's.

The skills `/wish` routes through are tightened first, so the entry point is not
built on stale or bloated instructions.

## Non-goals

- No new runner, script, or hook; `/wish` is instructions that route to existing skills.
- No change to `/prw` stage rules, merge authority, or review quorum.
- Not a replacement for `/superpowers-quick` (planning-only) or `/user-story` (docsets).

## Acceptance

- `/wish`, `/w`, and `/wq` each resolve to `.claude/skills/wish/SKILL.md` and forward arguments
  (checked by the thin-dispatcher validator).
- The skill defines three size tiers with the spec, exit-criteria, plan, and long-run tools each tier uses.
- The skill always calls for brainstorming and a no-code spec, and calls for UI mocks
  for user-facing changes.
- The skill routes every PR through `/prw` and calls for checkpoint pushes.
- Every skill named in the request's notes is linked where it applies, or reported as unavailable.
- Portability scans pass: no personal names, emails, or home paths.

## User stories

- As a developer with a quick fix in mind, I want `/wq fix the typo in the login error`
  to produce a ten-line spec and one PR, so that I am not buried in ceremony.
- As a developer starting a multi-day feature, I want `/wish` to produce a full no-code spec,
  mocks, an ironclad contract set as my goal, and a bead plan, so that the work survives
  session loss and has a clear stop condition.
- As a reviewer, I want every wish PR to follow `/prw`, so that its stage, evidence,
  and review state read the same as every other PR.

## Proof plan

Structural: `tests/test_thin_command_dispatchers.py` and the portability/PII scans pass.
Behavioral wording is reviewed by humans and LLM review, per the repository testing policy;
no wording-pin tests are added.

## Mock (command-line transcript)

```
> /wq add a dark-mode toggle to settings
Tier: S (one screen, one PR) — single settings surface, no data migration.
Spec: ~/roadmap/wish-dark-mode-toggle-2026-11-04.md
Mocks: M1 settings (toggle off, proposed), M2 settings (toggle on, proposed)
Auto-picked: default follows system theme (safest reversible); toggle persists per device.
PR: #123 [cd] Add dark-mode toggle to settings [coding] — draft, via /prw
```

## Risk

Low. Instruction-only change. The main risk is the skill contradicting a child
skill's contract; mitigated by linking to child skills rather than restating their rules.
