---
name: wish
description: Use when the user invokes /wish, /w, or /wq with a task or project idea. Turns the wish into a size-appropriate no-code spec (plus UI mocks for anything user-facing), a plan, implementation, and PRs through /prw. /wq is wish-quick - the LLM makes every judgement call and asks no questions.
---

# /wish — idea to shipped PR, sized to the task

`/wish <idea>` · `/w <idea>` (alias) · `/wq <idea>` (wish quick)

A wish is an authorized request to get the outcome done: spec it, plan it, build
it, and land it as PRs through `/prw`. The ceremony scales with the task size;
small wishes stay small.

## Modes

| Mode | Questions | Judgement calls |
|------|-----------|-----------------|
| `/wish`, `/w` | At most one batched round, and only for a decision that is genuinely the user's (taste, scope, money, irreversible or outward-facing actions). Everything else is decided from evidence. | LLM, recorded as assumptions. |
| `/wq` | No optional preference or clarification questions. Required authorization remains a blocker under the safety limits below. | LLM makes all of them: pick the recommended option, or the safest reversible one when evidence is thin, and record it. |

Both modes keep normal safety limits: no credentials, no destructive or
irreversible actions, no merging, and no scope expansion beyond the wish. A
blocker that only the user can clear is reported, never guessed around; other
independent work continues.

## Workflow

### 0. Resume before you restart

Look for earlier work on the same wish before writing anything new: existing
wish documents under the roadmap destination, open PRs and branches with the
topic, related beads, and prior sessions via [`/history`](../conversation-history-sparse/SKILL.md)
and [`/ms`](../memory-search/SKILL.md) when they are installed. If work exists,
continue it from its current state and say so. Re-read live state (git, PR,
CI) rather than trusting old prose.

### 1. Size the task

Pick one tier from the evidence (files touched, surfaces, unknowns, number of
PRs, wall-clock). Record the tier and the reason in the spec. When in doubt
between two tiers, pick the larger one for planning and the smaller one for
PR count.

| Tier | Shape | Spec | Exit criteria | Plan | Long-run tools |
|------|-------|------|---------------|------|----------------|
| **S** — small | ≤ a few hours, one PR, one surface | Short no-code spec (≤ 1 page) | 3–5 observable checks in the spec | Inline task list | — |
| **M** — medium | About a day, 1–3 PRs | Full no-code spec + short tech design | [`/ironclad`](../ironclad/SKILL.md) contract | [`superpowers-writing-plans`](../superpowers-writing-plans/SKILL.md) plan with TDD steps | [`/timeline`](../timeline/SKILL.md), [`/parallel`](../parallelize-to-ceiling/SKILL.md) |
| **L** — large | Days, many PRs or lanes | Full no-code spec + tech design + user stories | Full `/ironclad` contract, set as the session goal with [`/cmux-goal`](../cmux-goal/SKILL.md) | [`/plan-micro`](../plan-micro/SKILL.md) bead plan | `/timeline`, `/parallel`, [`/swarm`](../swarm/SKILL.md) for fan-out, beads for durability |

`/cmux-goal` applies only inside cmux; elsewhere use the host's own `/goal`
when it exists, or keep the ironclad contract as the stop condition.

### 2. Brainstorm (always)

Run the Superpowers brainstorming flow: the installed `superpowers:brainstorming`
skill when present, otherwise [superpowers-brainstorming](../superpowers-brainstorming/SKILL.md).
For `/wq`, apply the [superpowers-quick](../superpowers-quick/SKILL.md)
auto-pick contract: answer each question yourself and record question, choice,
and rationale under `Assumptions and Recommended Defaults`. For tier S, keep the
brainstorm to a few lines; do not run the full architectural path.

### 3. Write the no-code spec (always)

The spec says what changes for the user or operator, never how the code does
it. Follow the [`/user-story`](../user-story/SKILL.md) zero-code law: no
function, file, API, schema, or framework names; every acceptance criterion is
something a person can see, hear, or do. Include failure and empty states.

Sections, scaled to the tier:

1. **Wish** — one sentence, plus the tier and why.
2. **Outcome** — what is different when this is done.
3. **Acceptance criteria** — observable checks (tier S stops here plus mocks).
4. **User stories** — tier M and L; `/user-story` form.
5. **Out of scope** and **Assumptions and Recommended Defaults**.
6. **Exit criteria** — tier M and L; the `/ironclad` contract or a link to it.

Write it to the roadmap destination used by `superpowers-quick`
(`~/roadmap/wish-<topic>-YYYY-MM-DD.md`, resolved through [roadmap](../roadmap/SKILL.md)).
If that destination is unavailable, write it under the target repository's
existing docs or plans directory and say where.

### 4. UI mocks for anything user-facing (always)

If the wish changes what a person sees or does in a rendered interface, the spec
ships with mocks before implementation starts:

- One mock per changed screen and per meaningful state (empty, loading,
  populated, error, disabled, success). Group states that render the same.
- Mocks of screens that do not exist yet are labelled **proposed**. A screen
  that already exists is captured from the running product first; a drawn mock
  never stands in for it.
- Use HTML or ASCII mocks, matching the repo's design system when it has one
  ([frontend-design](../frontend-design/SKILL.md) for new visual work). Cite mocks
  from acceptance criteria ("see M2").

Command-line and API-only changes get a transcript-style mock of the input and
output instead.

### 5. Tech design and plan

- Tier S: a short task list in the spec; implement with TDD directly.
- Tier M: a short tech design section (approach, alternatives rejected, risks),
  then a `superpowers-writing-plans` plan.
- Tier L: [`/design-doc`](../design-doc/SKILL.md) or [`/engplan`](../engplan/SKILL.md)
  for the tech design, then `/plan-micro` for beads. Draw the schedule with
  `/timeline` and run independent lanes in parallel up to the `/parallel`
  ceiling; use `/swarm` when a lane set needs adversarial verification.

### 6. Build and land through `/prw`

Implement test-first. Every PR follows [`/prw`](../prw/SKILL.md) (draft first,
the repository's stages, evidence, review route, readiness). Split work into PRs
by the plan, not by convenience; small wishes are one PR.

- **Checkpoint pushes**: commit and push work in progress to the draft PR at each
  milestone, and never hold more than about ten minutes of unpushed work. Quota
  or session loss must not lose the work.
- **Evidence**: prove each acceptance criterion with the cheapest evidence that
  settles it, per [evidence-standards](../evidence-standards/SKILL.md). UI
  criteria need real captures of the built screens next to the mocks.

### 7. Finish

Done means every exit criterion is met with evidence, every PR is green and in
the state `/prw` defines as ready, and the spec reflects what shipped. Then:

- Run [`/learn`](../learn/SKILL.md) for any durable lesson the work produced.
- Report: tier and why, spec and plan paths, mock paths, PR links and states,
  questions auto-picked (with `/wq`) or asked (with `/wish`), and anything still
  blocked with its exact owner.

## Rules

- The spec comes before code, at every tier. A tier S spec can be ten lines.
- Do not inflate a small wish into a project or shrink a project into one PR.
- A wish never grants merge authority; `/prw` merge rules still apply.
- Skill not installed? Name it as unavailable and continue with the closest
  step this file describes; never invent a substitute that claims its gate.
