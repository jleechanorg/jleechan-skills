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

When invoked, execute this sequence **in full, every time**:

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
- **Refuse-by-confabulation** — agent cites a fabricated "policy" or "constraint" to justify refusing a task instead of attempting and reporting; usually triggered by misreading a skill clause (e.g. "no login bypass" → "this site only"). Example: on 2026-06-21, refused to use browserclaw to add OAuth redirect URIs to GCP Console, citing a non-existent policy that "it can only navigate the app and its auth handshake, not external GCP Console." The actual skill supports any-website capture via `--storage-state` and the "no login bypass" clause is about authentication, not site scope. The fix is to read the actual skill/help file before refusing, and quote the exact line if a constraint is real.

**Coordinator-gate variant:** Before requiring extra coordinator permission, cite the exact governing
instruction or current human hold and its scope. For a claimed resource collision or execution failure,
identify the concrete resource, conflicting operation/owner, and current evidence; a shared account alone is
not a collision. Distinguish campaign state, global settings, browser profile, device, and evidence baseline
overlaps. Unknown occupancy is not an authentication failure; unknown coordinator state alone must not block
otherwise authorized work. Authorized work without verified live competing use proceeds to real auth
preflight; reservation, admission, and handback labels are never prerequisites. Preserve injected
authentication-error propagation, verified conflicting operators, explicit current human holds, and
listener/bundle/source identity checks; never bypass an actual denial or infer release from silence.

**Observed case (2026-10-24, `creation ui`) and its loophole closers.** A lane waited 22 h because its
launcher required a Scene ledger state of exactly `admitted` before authentication, and its regression tested
enforcement of that invented gate instead of its authority. Close the two loopholes when applying this rule:
another lane merely being **alive** on a shared account is not a conflict — only mutation of the *same
mutable target* (same campaign/document id, same account-wide setting, same browser profile dir, same
simulator UDID) is; and **unknown occupancy must proceed to preflight**, not pause. When unblocking such a
lane, require a **case-by-case audit**: `git diff` its launcher/preflight/tests, list every scheduling-state
predicate (`admitted`/`reserved`/`handback`/`held`), and for each one decide with evidence whether it is an
*invented* gate (remove it) or a real safeguard (keep it). **A missing policy `file:line` is a signal to
investigate, never proof that a safeguard lacks authority** — do not delete on absence of a citation.
Preserve explicitly: a current human STOP referenced by message, real access/auth denials, one-writer
ownership of a branch/PR/worktree, and the user's shared execution budget (quota/time-box). Only remove a
gate after showing it was derived from coordinator scheduling language, and only change a regression test
that encoded that invented gate.

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
   - Is the rule already documented? If yes → it's an adherence problem, add a stronger enforcement instruction
   - If no → add the rule
2. **Check for existing skills** — `~/.claude/skills/`, `~/.claude/commands/`
   - Is there a skill that should have caught this? If yes → update it
   - If no and the pattern is repeatable → create a skill
3. **Check memory** — `~/.claude/projects/*/memory/`
   - Was this corrected before? If yes → the memory wasn't sufficient; strengthen it
   - If no → save feedback memory
4. **Check tests** — are there tests that would catch this regression?
   - If no → propose an integration test
5. **Check CI** — would CI have caught this before merge?
   - If no → propose a CI gate or pre-commit hook

**Critical check — harness layer present but broken:**
For each harness layer that exists, verify it **actually works**, not just that it exists. A broken guardrail is as bad as a missing one and is harder to detect.

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
- Apply all harness fixes
- Run verification
- Report what was changed

## Decision Rules

- **If the same correction has been given twice**: This is a mandatory harness fix. No exceptions.
- **If the fix is a one-liner in code but the pattern could recur**: Harness fix first, code fix second.
- **If unsure whether it's a harness gap or a one-off**: Ask the user. Don't assume one-off.
- **Never add instructions that duplicate what's already documented**: Check first.
- **Prefer the most durable layer**: Instructions > Skills > Memory > Tests > CI
- **5 Whys are mandatory**: Never skip them. Short-circuit analysis produces shallow fixes.
- **Agent path is mandatory**: Never analyze only the technical dimension. Always ask why the agent failed too.

## Quick examples (compact form)

**User says "don't mock the database in these tests"**:
→ Failure class: wrong approach
→ 5 Whys technical: mock used → no instructions prohibiting it → testing philosophy not documented → ...
→ 5 Whys agent: agent defaulted to mock → common pattern in training data → no skill redirecting to real tests → ...
→ Add instruction to CLAUDE.md, save feedback memory

**Test labeled "e2e" but only does unit-level work**:
→ Failure class: mislabeled artifact
→ 5 Whys technical: E2E criteria not met → criteria not checked → no checklist for E2E → ...
→ 5 Whys agent: agent named it e2e without verifying → no skill mandating verification → ...
→ Add/update test classification rules in CLAUDE.md + AGENTS.md, update /validate-e2e skill

**Same code review comment given 3 conversations in a row**:
→ Failure class: repeated manual fix → mandatory harness fix, no exceptions
→ Add instruction to CLAUDE.md, save memory, consider lint rule

**Automation cleanup silently fails every cycle**:
→ Failure class: silent degradation (harness layer present but broken)
→ 5 Whys technical: cleanup fn uses wrong grep key → porcelain format not verified → no test for cleanup path → ...
→ 5 Whys agent: agent said "cleanup present" without running it → assumed present = working → skill doesn't mandate verifying harness script correctness → ...
→ Fix script, add verification step to skill, add integration test for cleanup path

**AO worker spawned on original PR branch instead of isolated clone**:
→ Failure class: LLM path error — wrong abstraction level (agent acted at "spawn worker" level without verifying branch isolation)
→ 5 Whys technical: `ao spawn` reuses existing worktrees → `--claim-pr` only adds dashboard tracking → no clone created → worker lands on original branch → pushes commits directly to live PR
→ 5 Whys agent: request said "spawn for PR 6198" → agent assumed `ao spawn` would create isolation → flag name implies PR association but not branch isolation → no skill/instruction to redirect to clone-before-spawn → harness had no rule for this failure class
→ Fix: add clone-before-spawn rule to jleechanclaw CLAUDE.md, add verification to team-mini.md, add failure class to harness.md, save feedback memory

**General principle — tool semantic mismatch**: many tool names imply
capabilities they don't actually provide (`ao spawn --claim-pr` implies PR
isolation but provides only dashboard tracking; `git checkout -b` implies a new
branch but can be from HEAD, not an isolated PR clone; `gh pr checkout` checks
out the PR branch directly, not a clone). When a tool's name semantically
promises isolation or safety guarantees, verify those guarantees exist in the
implementation before relying on them — if the name over-promises relative to
behavior, the harness gap is the misleading name, fixed in docs/skill rather
than expecting agents to discover the gap on their own.

## Example failure pattern: CLI redacts secrets but scripts still export them

**Observable:** Gateway returns `unauthorized` / embedded fallback; logs show token value `__OPENCLAW_REDACTED__` or similar.

**Failure class:** **Silent degradation** (harness script looked correct: “get token, export, run”) plus **knowledge gap** (CLI intentionally does not echo real secrets).

**Technical 5 Whys (compressed):** Export used `openclaw config get …` → CLI prints redacted sentinel → shell passed sentinel to gateway → auth failed → embedded fallback.

**Agent 5 Whys (compressed):** Pattern “export token then call CLI” is common in docs → agent did not verify the *value* was non-redacted → no instruction forbidding export of `config get` for secrets → recurrence.

**Harness fixes (typical):**
1. **Instructions** — `~/.claude/CLAUDE.md`: never `export` gateway tokens from `config get` when output can be redacted; `unset` override env vars; read JSON or use provider-specific keys (`MINIMAX_API_KEY`) as documented.
2. **Commands** — `~/.claude/commands/claw.md` (or repo overlay): validate token with a file read / non-redacted check; document the redaction trap explicitly.
3. **Memory** — one-line feedback memory so project agents see it in `MEMORY.md`.

**Verification:** Run the command path and confirm the exported string is not a known redaction sentinel and gateway returns `status: ok` without “falling back to embedded”.

## Historical failure pattern: retired Gate 7 trusted aggregate workflow status

**Historical observable:** before the 2026-07-28 policy change, an agent trusted
Green Gate `completed/success` while a separate Skeptic verdict was missing.
This mechanism is retired; current policy is the canonical two-gate `/green`.

**Failure class:** **Silent CI success** — a workflow can exit 0 at the job level while an inner step fails. The harness layer (Green Gate) is present and running, but it reports the wrong thing at the job level.

**Technical 5 Whys:**
1. Why did the PR show Green Gate `completed/success` even though Gate 7 was failing?
2. Why does the workflow exit 0 at job level even when the VERDICT check step exits 1?
3. Why is the VERDICT check inside a step rather than as a separate job with its own status?
4. Why does the polling step swallow the step failure without propagating it to job status?
5. Why is there no CI gate that independently verifies VERDICT existence as a separate job?
→ Root cause: The Green Gate conflates “trigger posted” with “skeptic evaluated”; the job always exits 0 because the trigger step succeeds, and the VERDICT step failure is swallowed inside the job.

**Agent 5 Whys:**
1. Why did the agent trust `gh pr checks` output to determine Gate 7 status?
2. Why didn't the agent read the workflow log to verify gate outcomes?
3. Why was there no instruction telling the agent that `gh pr checks` is insufficient for Gate 7?
4. Why did the existing 7-green definition not include a verification procedure for Gate 7?
5. Why was the skill written as policy without a mandatory verification step?
→ Agent root cause: The harness defined 7-green as policy without requiring independent VERDICT verification, so agents trusted the workflow's job-level status.

**Harness fixes:**
1. **Skill** — `pr-green-definition.md`: Add mandatory REST API VERDICT check procedure (not just policy statement)
2. **Skill** — `pr-green-definition.md`: Add counter-example showing Green Gate `completed/success` while Gate 7 fails
3. **Command** — `/green.md`: Already exists but relied on workflow logs only; updated to mandate REST check for Gate 7
4. **Memory** — `feedback_2026_04_21_silent_ci_success.md`: Document the specific PRs where this was observed

**Current verification:** follow
`~/.claude/skills/pr-green-definition/SKILL.md`; independently verify
current-head CI conclusions and mergeability rather than trusting the Green Gate
display status.

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
- never make direct user-scope edits from the scheduled run;
- never require beads, `/nextsteps`, a frozen evaluation corpus, AO workers, or
  unrelated process changes as prerequisites.

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

Unless invoked with `--fix`, do not edit the harness. Audit, create the durable
recommendation, and stop.

## Anti-patterns

- Adding a memory entry when the fix should be an instruction (memory is per-project; instructions are global)
- Writing a skill for a one-time operation
- Adding an integration test without also fixing the instruction that led to the bug
- Proposing CI gates for things that should be caught at the instruction level
- Over-engineering: adding 5 harness layers when 1 instruction would suffice
- Skipping the agent 5 Whys because "the technical fix is obvious"
- Assuming a harness layer works because it exists — verify it
