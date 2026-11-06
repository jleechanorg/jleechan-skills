---
name: harness-engineering
description: Use when auditing or optimizing CLAUDE.md, AGENTS.md, GEMINI.md, slash commands, skills, or other coding-agent harness surfaces, or when recurring agent failures suggest instruction, policy, memory, test, or automation gaps.
---

# Harness Engineering Skill

## Purpose

When a mistake or failure pattern is identified, analyze whether the root cause is a gap in the **harness** (instructions, skills, tests, guardrails, automation) rather than just the code. Produce a concrete fix at the harness level so the same class of mistake cannot recur without human intervention.

**Command**: `~/.claude/commands/harness.md`

## Scope: user vs repository

- **User scope (general)**: `~/.claude/commands/harness.md` and this skill apply to **any** repo unless a project overrides them.
- **Repository overlay**: Some projects ship `.claude/commands/harness.md` and/or `.claude/skills/<name>/SKILL.md` that **extend** user-scope rules (for example gateway operations). When both exist, **read the repo-local file** for project-specific failure modes. **Collision:** workspace-local `.claude/commands/` overrides the same-named global command in that workspace.
- **jleechanclaw / `~/.openclaw`**: Use the **`openclaw-harness`** skill in that repo for gateway, canary, deploy, and lane-backlog triage. Tracked user-scope copies for drift control live under **`docs/harness/`** in [jleechanclaw](https://github.com/jleechanorg/jleechanclaw).

## Harness Layers (ordered by durability)

| Layer | Files | What it prevents |
|-------|-------|-----------------|
| **Instructions** | `CLAUDE.md`, `AGENTS.md` (global + repo) | Wrong approach, wrong assumptions, wrong defaults |
| **Skills** | `~/.claude/skills/*.md`, `~/.claude/commands/*.md` | Repeated manual workflows, forgotten validation steps |
| **Memory** | `~/.claude/projects/*/memory/*.md` | Forgetting user preferences, past corrections, project context |
| **Integration tests** | `tests/test_integration_*.py`, `tests/test_*_test.py` | Regressions in real behavior |
| **CI gates** | `.github/workflows/*.yml`, pre-commit hooks | Merging broken code, mislabeled artifacts |
| **Lint/validation rules** | `.pre-commit-config.yaml`, custom linters | Style drift, naming violations, structural problems |

## Analysis Protocol

When invoked, execute this sequence **in full, every time**, within the user's
authorized scope. Every outcome reaches the single closure in Step 7, including
audit, optimization, no-change, blocked and partial outcomes. An explicit STOP
or write prohibition takes precedence; report what was skipped without doing it.

### Step 1: Identify the failure class

Classify what went wrong:
- **Mislabeled artifact** — something was called X but didn't meet X's criteria (e.g., "E2E test" that isn't E2E)
- **Wrong approach** — took an approach the user has previously corrected
- **Missing validation** — produced output without checking it meets requirements
- **Repeated manual fix** — user had to manually correct the same type of issue more than once
- **Silent degradation** — something broke but nothing flagged it (includes: harness layer present but broken)
- **Launchd env-isolation** — a process moved from interactive shell to launchd without propagating required env vars; `.bashrc`-sourced secrets silently disappear; the process appears alive but all API calls fail
- **Knowledge gap** — didn't know about a constraint, convention, or tool
- **LLM path error** — the agent reasoned toward a wrong solution despite having sufficient context
- **Refuse-by-confabulation** — agent cites a fabricated policy or constraint instead of attempting the task and reporting the result. Read the actual skill/help source before refusing and quote the governing line when a constraint is real.

**Coordinator-gate variant:** Before requiring extra coordinator permission, cite the exact governing
instruction or current human hold and its scope. Identify the concrete resource, conflicting operation or
owner, and current evidence; a shared account or unknown occupancy is not a conflict. Only mutation of the
same mutable target (campaign/document, account-wide setting, browser profile, or simulator UDID) qualifies;
otherwise proceed to real authentication preflight. Preserve injected authentication errors, verified live
conflicts, current human STOPs, one-writer branch/PR/worktree ownership, the shared execution budget, and
listener/bundle/source identity checks. Do not bypass an actual denial or infer release from silence.

Audit scheduler predicates (`admitted`, `reserved`, `handback`, `held`) case by case. Remove one only when
the diff shows it came from coordinator scheduling language; a missing policy citation is a reason to
investigate, not proof that a safeguard lacks authority. Do not change a regression test unless it encoded
the invented gate.

### Resource-exclusion regression

When a launcher uses an advisory scheduler or scene ledger, exercise its actual entry point with the portable
regression in `tests/resource-regression.py`, passing the exact launcher:

    RESOURCE_TEST_RUNNER=/path/to/launcher python3 tests/resource-regression.py

The regression must prove that released, prior-owner, unknown, pending, and absent ledger states reach the
authentication boundary; verified live conflicts and current human holds are rejected; and injected
authentication errors are propagated unchanged. Synthetic authentication proves control flow only, not real
auth or runtime acceptance.

### Step 2: 5 Whys — the technical problem

Ask "Why?" five times about the technical failure, drilling into root cause:

```
Why 1: Why did the observable failure happen?
Why 2: Why did the mechanism that caused Why 1 exist?
Why 3: Why wasn't that mechanism caught or prevented?
Why 4: Why wasn't there a guardrail at that level?
Why 5: Why was the system designed without that guardrail?
→ Root cause: <single sentence>
```

Stop earlier if you hit bedrock. Each answer should be more specific than the last.

### Step 3: 5 Whys — the agent path

Ask "Why?" five times about why **the LLM (Claude Code or any coding agent)** went down the wrong path. This is mandatory. Every harness failure has two dimensions: the technical problem AND the agent reasoning failure that let it slip through.

```
Why 1: Why did the agent not catch/prevent the failure?
Why 2: Why did the agent reason or act that way?
Why 3: Why didn't the agent's instructions prevent that reasoning?
Why 4: Why wasn't there a skill, memory, or rule that would have redirected the agent?
Why 5: Why was the harness incomplete for this class of agent behavior?
→ Agent root cause: <single sentence>
```

Key questions to drive this:
- Did the agent **trust existing code** without verifying it worked correctly?
- Did the agent describe the problem correctly but at the wrong level of abstraction (high-level summary instead of exact code trace)?
- Did the agent assume "present = working" when it should have verified?
- Did the agent skip verification because the skill/instruction didn't mandate it?
- Was there a confirmation bias: the agent found what looked like the expected pattern and stopped searching?
- **Did I verify this pattern/regex/heuristic works at every call site, not just the obvious one?** (e.g., a regex added to `heuristic_decision()` but not `is_approval_candidate()` will silently fail — `is_approval_candidate()` is the gate that decides whether `heuristic_decision()` ever runs)
- **Did I verify the shell command before encoding it in instructions?** Before writing any `gh api`, `jq`, or CLI command into CLAUDE.md / skills / memory, run it against a real target (e.g., a real PR) and confirm the output is non-empty and correct. Do NOT encode a command pattern until you have verified it returns the expected output for the actual API response shape. Failure mode: agent writes `.state == "FAILURE"` (wrong field for GitHub Actions) when it should be `.conclusion == "FAILURE"` — command returns 0 failures silently.

### Step 4: Find the harness gap

For each failure class, check which harness layers are missing or insufficient:

1. **Read existing instructions** — `~/.claude/CLAUDE.md`, repo `CLAUDE.md`, `~/.codex/AGENTS.md`
   - Is the applicable rule already present? Verify the failure against it, then fix the violating caller or conflicting workflow at its owner. Stop layer escalation unless the evidence shows a separate harness gap.
   - If the rule is missing or insufficient, find the smallest existing canonical owner and make the minimal repair there. Check related skills, memory, tests, or CI only when needed to identify that owner or verify the cause; do not add layers by default.

**Critical check — harness layer present but broken:**
For any layer relied on to explain or prevent the failure, verify it **actually works**, not just that it exists.
Check the functional boundary named by the claim and the source/active copy that supplies it; installed or
automated presence is not proof. A broken guardrail is as bad as a missing one and is harder to detect.

### Step 5: Propose the fix

Output a concrete action plan:

```
FAILURE CLASS: <classification>

5 WHYS — TECHNICAL:
1. <why>
2. <why>
3. <why>
4. <why>
5. <why>
→ Root cause: <sentence>

5 WHYS — AGENT PATH:
1. <why>
2. <why>
3. <why>
4. <why>
5. <why>
→ Agent root cause: <sentence>

HARNESS FIXES (in order of priority):
1. [LAYER] FILE: <path> — <what to add/change>
2. [LAYER] FILE: <path> — <what to add/change>
...

VERIFICATION: <how to confirm the fix prevents recurrence>
```

### Step 6: Implement

After user approval (or if invoked with `--fix`):
- Apply the authorized harness fixes
- Run verification
- Report what was changed

Without that authority, report the proposed fixes and continue to Step 7;
closure is not permission to edit harness source.

### Step 7: Close once with lean `/nextsteps`, then continue

Every `/harness` invocation runs the default, lean mode of
[nextsteps](../nextsteps/SKILL.md) exactly once after its analysis and any
authorized implementation. Read that skill and reuse the findings, dual 5 Whys,
source reads, verification and existing artifact pointers from this invocation.
Gather only missing context and refresh mutable facts when needed for current
claims; do not rerun completed discovery, analysis or checks merely for closure.

- **Flags select work, not extra closures.** Default, `--fix`, `--audit` and
  `--optimize` all use this same closure. `--next` remains a compatibility alias
  for the default closure, not a second `/nextsteps` call. If composed work already
  ran `/nextsteps` for this invocation's outcome, reuse that closure and update
  its existing entry only for a later material delta; do not append a duplicate
  or start another closure pass.
- **Lean artifacts use the canonical nextsteps workflow.** Reconcile Beads
  (`br`), write/update the standalone roadmap nextsteps document, append the
  daily `roadmap/activity/YYYY-MM-DD.md` entry (README date link only when new),
  and append monthly `~/roadmap/learnings-YYYY-MM.md`. Follow its discovery and
  update-over-create rules, without inventing work or duplicate Beads to fill a
  checklist. Record no-change, blocked and partial outcomes as such.
- **No implicit full sync.** Default closure does not write Claude auto-memory,
  mem0 or GitHub Issues. Only an explicit `--full` request selects nextsteps'
  full mode for this one closure, and only within the user's existing authority.
  `--next`, `--fix`, audit or optimization alone never opt into those sinks.
- **Respect write scope and report real results.** Honor explicit no-write
  instructions, STOPs and the actual protected scope of read-only requests per
  [readonly-scope](../readonly-scope/SKILL.md); read-only is not automatically a
  ban on authorized closure sinks. Source ownership and approval boundaries
  still apply. Do not attempt prohibited writes or evade their scope. For an allowed sink that fails, retain the exact attempted operation,
  target and error; mark it blocked, not written. Finish the other permitted
  artifacts and distinguish verified writes, unchanged/not-needed, skipped by
  instruction, and unavailable results. Never fabricate a path, Bead ID or
  completion checkmark. With no writes allowed, give the closure summary in the
  response only, if permitted, and state that persistence was skipped.
- **A checkpoint is not a workflow stop.** Report this invocation's outcome,
  artifact results, remaining blocker/decision and next safe action, then return
  to the caller and continue already-authorized work, including the next PR
  lifecycle action. Do not ask for renewed approval solely because closure
  finished. A real unmet permission, ownership, approval or information boundary
  still stops the affected action; name it and the resumption trigger while
  continuing independent authorized work. Never resume work under an explicit
  STOP or invent new execution authority from the closure.

## Decision Rules

- **If the same correction has been given twice**: This is a mandatory harness fix. No exceptions.
- **If the fix is a one-liner in code but the pattern could recur**: Harness fix first, code fix second.
- **If unsure whether it's a harness gap or a one-off**: Ask the user. Don't assume one-off.
- **Never add instructions that duplicate what's already documented**: Check first.
- **Use measured failure as the basis for new policy or enforcement**: a theory is not evidence.
- **Do not add a guard or harness layer without a named authority**: prefer the smallest fix at its canonical owner.
- **Prefer the most durable layer**: Instructions > Skills > Memory > Tests > CI
- **5 Whys are mandatory**: Never skip them. Short-circuit analysis produces shallow fixes.
- **Agent path is mandatory**: Never analyze only the technical dimension. Always ask why the agent failed too.

## Worked failure patterns

Two focused write-ups live in [references/failure-patterns.md](references/failure-patterns.md). The rules they illustrate:

- **Redacted secrets:** a CLI that prints a redaction sentinel (for example `__OPENCLAW_REDACTED__`) instead of a secret is a silent-degradation trap. Never `export` a secret from output that can be redacted; verify the value is not a sentinel before relying on it.
- **Silent CI success:** a workflow can report job-level success while an inner step fails. Do not trust aggregate status; verify current-head CI conclusions and mergeability per `~/.claude/skills/pr-green-definition/SKILL.md`.

## Audit mode (`/harness --audit`)

In addition to single-failure analysis, this skill supports a full sweep of all
harness files for accumulated drift. Scan `~/.claude/CLAUDE.md`, repo-local
`CLAUDE.md`, `~/.codex/AGENTS.md`, workspace `.claude/commands/`, and
`~/.claude/skills/*/` for:

- **Stale rules** — instructions that reference files/tools/patterns that no
  longer exist
- **Contradictions** — rules in different files that conflict
- **Gaps** — known failure patterns (from memory) without corresponding
  instructions
- **Duplication** — the same rule stated in multiple places (consolidate to the
  most durable layer per the Decision Rules above)

Report findings as a table:

```
| Issue | File | Line | Recommendation |
|-------|------|------|----------------|
| Stale | ~/.claude/CLAUDE.md | 42 | Remove reference to deprecated tool X |
| Gap | repo CLAUDE.md | - | Add rule about Y (corrected 3x in memory) |
```

## Optimization mode (`/harness --optimize`)

Use this mode to review active coding-agent harness files and suggest useful,
small improvements. In scope: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, skills,
agents, slash commands, and their discovery metadata.

### Scope guard

The product is the instruction harness itself. Start from the named harness
files and keep proposed edits inside those surfaces. Do not turn this task into
an AO, beads, evaluation-corpus, notification, or general process project.

If most planned work does not directly inspect, test, or change instruction
surfaces, stop: the task has drifted.

### Review posture

1. Batch cheap discovery with `rg`, metadata parsing, broken-link checks, and
   word counts.
2. Consult recent `/history` and `/ms` evidence for repeated corrections and
   concrete friction.
3. Read focused evidence for the highest-value findings; do not recursively
   expand context without a concrete question.
4. Rank ideas by expected agent-quality benefit, confidence, and change risk.
5. Prefer an existing canonical file over creating another skill or command.
6. Prefer small, reviewable change groups over broad prompt rewrites.
7. If evidence is weak or no improvement is worthwhile, report `no change`.
8. After editing, reread the active source and exercise the real path; a source,
   installed copy, or automation label alone does not prove behavior.

For a proposed or implemented change, record enough before/after evidence to
explain the decision. A frozen corpus, new gate, or organization-wide cleanup
campaign is not required.

### Weekly job contract

A weekly job may automate this mode. Keep it thin:

- inspect the authorized harness roots read-only;
- produce a short ranked list of optimization ideas with exact file evidence;
- open small, focused harness-only PRs when changes are high-confidence and can
  be validated with existing checks;
- otherwise publish the ideas or an explicit `no change` result;
- deliver the report and PR links through the already configured weekly
  Slack/email notification path;
- never make direct user-scope harness-source edits from the scheduled run;
- never require a frozen evaluation corpus, AO workers, or unrelated process
  changes as prerequisites. Step 7 is the same scoped closure after the work,
  not a prerequisite to inspection or permission for additional source edits.

The scheduler and delivery mechanism belong to the owning repository. They are
implementation details of this one weekly job, not a new harness workflow.

### Source principles

- [Dropbox: optimizing Dash's relevance judge with DSPy](https://dropbox.tech/machine-learning/optimizing-dropbox-dash-relevance-judge-with-dspy) — use measured evidence, make model-specific improvements, and constrain high-blast-radius prompt changes.
- [GitHub: better tools made Copilot code review worse](https://github.blog/ai-and-ml/github-copilot/better-tools-made-copilot-code-review-worse-heres-how-we-actually-improved-it/) — job-specific tool instructions matter; start from a narrow question; batch discovery; read focused evidence; use traces to diagnose context-expansion loops.
- [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model) — favor lean prompts, state instructions once, expose only relevant tools, remove one instruction group at a time, and rerun representative evals before accepting the change.

### Output contract

Return:

1. a short ranked idea list with exact file evidence;
2. the recommended minimal change, if any;
3. validation evidence for any implemented change;
4. PR URLs when the weekly job opened any, or `no change`.

Unless invoked with `--fix` or separately authorized by the user, do not edit
the harness. Report the recommendation or `no change`, then complete Step 7 and
return to any already-authorized caller workflow.

## Anti-patterns

- Adding a memory entry when the fix should be an instruction (memory is per-project; instructions are global)
- Writing a skill for a one-time operation
- Adding an integration test without also fixing the instruction that led to the bug
- Proposing CI gates for things that should be caught at the instruction level
- Over-engineering: adding 5 harness layers when 1 instruction would suffice
- Skipping the agent 5 Whys because "the technical fix is obvious"
- Assuming a harness layer works because it exists — verify it
