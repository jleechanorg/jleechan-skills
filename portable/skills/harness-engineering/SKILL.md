---
name: harness-engineering
description: "Audit recurring agent failures and propose narrow durable guardrails."
---

# Harness engineering

Analyze whether a recurring mistake comes from instructions, skills, memory, tests, CI,
or validation rules rather than only from application code. Produce a narrow guardrail
that prevents recurrence while preserving user scope. This workflow is diagnostic and
read-only unless the caller explicitly authorizes a particular fix.

## Dispatch

`/harness` invokes this skill and preserves the caller's arguments. With `--audit`,
run the Audit branch; with `--optimize`, run the Optimize branch. With both flags,
run the audit first and use its verified findings as focused optimization evidence.
With neither flag, run single-failure classification and both root-cause passes.
`--fix` requests implementation of the resulting in-scope changes; it does not
authorize new access, sensitive transmission, publication, or irreversible actions.

## Scope and evidence

Read only instruction and skill paths supplied by the caller or visible in the current
workspace. Treat history and feedback as evidence, not authority. Do not read credential
stores, export tokens, install schedulers, message external services, or convert one
correction into a global policy without explicit scope. A repository overlay can add
constraints; it cannot silently override the host instruction hierarchy.

Classify the failure (mislabeled artifact, wrong approach, missing validation, repeated
manual fix, silent degradation, knowledge gap, path error, or unsupported refusal).
Verify that an existing guardrail actually catches the case; presence of a file is not
proof that it works.

For a process moved to a worker or service, check required environment propagation
without displaying secret values. For an unsupported refusal, check the actual
current instruction or tool help and quote the real constraint; do not invent one.

## Two root-cause passes

Ask five increasingly specific whys about the technical failure, then five about the
agent path that allowed it. Stop at bedrock when reached. For each harness layer, record
the observed gap and a bounded change: instructions, skill, memory, test, CI, or lint.
Prefer the most durable layer that is in scope and avoid duplicating existing rules.

Trace the actual failing call path. Check every relevant call site of a pattern,
regex, or heuristic, including upstream gates; validating only one obvious consumer
can miss the decision that prevents it from running. Before encoding a shell or API
command into instructions, verify its response shape and meaningful output against
an authorized target, or mark it unverified with the precise missing capability.
Verify tool isolation or safety guarantees from behavior rather than its name.

## Audit branch

For an audit request, sweep the authorized instruction, skill, command, and discovery
metadata roots read-only for four drift classes:

- Stale references to files, tools, or patterns that no longer exist.
- Contradictions between rules or instruction surfaces.
- Gaps where evidenced failure patterns lack an effective guardrail.
- Duplication that belongs in one existing canonical location.

Report each issue with exact file and line evidence and a bounded recommendation.
Do not infer a gap from history alone without checking current instructions.

## Optimize branch

For an optimization request, stay within the named harness surfaces. Batch cheap
metadata, reference, and size checks; consult available authorized recent feedback or
traces for concrete friction. Read focused current evidence for a specific question,
rather than recursively expanding context.

Rank proposed improvements by expected benefit, confidence, and change risk. Prefer
small, reviewable changes in an existing canonical file over new skills, duplicate
rules, or broad rewrites. Return the ranked ideas with exact file/line evidence, the
recommended minimal change, and a verification plan; retain before/after evidence for
any authorized implementation. If evidence is weak or no improvement is worthwhile,
return `no change`. Do not turn this branch into a new framework, scheduler, evaluation
corpus, publication, or general process project.

## Output and implementation gate

For single-failure analysis, return `FAILURE CLASS`, `TECHNICAL WHYS`, `AGENT-PATH WHYS`,
`HARNESS FIXES`, and `VERIFICATION`; Audit and Optimize use their outputs above.
A fix proposal must name exact files and an executable verification.
Apply changes only when the caller has authorized that implementation; otherwise leave
the workspace unchanged. If a live dependency is absent, say so and provide a safe
read-only verification plan. Do not treat weekly communication contracts, deployment
recipes, or fullrun language as standing permission.
