---
name: root-cause-first
description: Use when a bug may cross an LLM/backend boundary or tempts changes to prompts, schemas, parsing, persistence, retries, fallbacks, guards, or response repair.
---

# Root Cause First

## Repository policy first

On every invocation, including a global slash command or an absolute global
skill path, locate the active repository and read its applicable `AGENTS.md` /
`CLAUDE.md` and scoped instructions before diagnosing or choosing a lane.

1. Check the repository's declared skill locations and canonical pointers,
   including `.claude/skills/root-cause-first/SKILL.md`,
   `.agents/skills/root-cause-first/SKILL.md`, and
   `.codex/skills/root-cause-first/SKILL.md` when present. Resolve wrappers and
   mirrors to their canonical source; do not count a mirror as another policy.
2. Read the repository-specific root-cause-first policy completely and follow
   its required companion discovery. **Repository policy is PRIMARY** over this
   portable reference for project-specific diagnosis, ownership, and evidence.
   This precedence never overrides higher-priority instructions, current user
   scope, safety, access controls, or mandatory confirmations.
3. Load that local policy once. If it reads this global file as a reference,
   continue below without rediscovering or reinvoking the local entrypoint.
   Likewise, lane skills referring back here reuse the current route verdict;
   reclassify only when new evidence changes the first divergence.
4. If no repository policy exists, explicitly report that none was found and
   the locations checked, then use this portable workflow. An unreadable policy
   is not an absent policy: report the access/missing-content gap, pause only
   decisions that depend on it, and continue independent authorized work.

Resolve required `llm-first`, `backend-first`, and `redgreen` (`/rg`) companions
from repository instructions first, then verified installed/global locations
(such as siblings of this skill). Read the selected owner's instructions before
execution. Do not silently replace a missing required companion or invent a
repository policy. A review may read companions to evaluate a claim without
executing their repair workflows.

## Rule

Diagnose before editing. This skill locates the first divergence and chooses one
causal lane. It does not tune prompts or change backend behavior itself.

## Modes

- **Direct diagnostic mode** applies when the active task asks to diagnose a
  concrete failure and authorizes investigation
  or fixes. After the route verdict, use the selected owner only for steps
  already authorized by that task; diagnosis alone does not authorize repairs.
- **Review-only mode** applies when the task requests a review or audit, including
  a diagnostic loaded by another review workflow. Reviewing a diff, PR, guard,
  or proof does not itself authorize repairs. Emit the evidence-backed verdict
  and findings, then
  stop before executing `/llm-first` or `/backend-first`. Return those findings
  to the parent workflow; completing this review does not end other authorized
  work in the parent task.

Resolve the mode from the active task. A request to diagnose authorizes
investigation, not every possible fix or production mutation. If the task is
review-only or its scope remains unclear, return the verdict to the caller and
continue only the caller's already-authorized work.

## Reachability and fresh RED/GREEN

Before a behavior fix, identify the reachable user flow, violated contract,
current base/head revisions, and existing PRs or active owners touching the
same path. Compare proposed work with those PRs before writing; avoid competing
fixes. A source-level suspicion is not proof that the user flow reaches it.

In an authorized fix lane, use `/rg` (the verified redgreen owner) to execute a
fresh causal failing test before changing behavior, then rerun the same check
and relevant regressions after the narrow fix. Record commands, timestamps,
baseline/candidate revisions, artifacts, and the tested process's true exit
status; a successful log/tee command is not a test pass. A missing dependency,
historical incident, unrelated assertion, or source-string match alone does
not establish the reported runtime failure. Keep synthetic/captured-fixture,
real-server, and live-provider claims separate.

Review-only mode audits this evidence without launching fixes or experiments.
Missing causal RED blocks the dependent fix, not independent investigation.
Choose the lowest sufficient evidence layer; this skill neither mandates a
paid experiment nor authorizes provider requests, retries, publication, or
production writes.

## Boundary trace

Capture the same failing turn across these checkpoints:

1. Intended agent, prompt, schema, provider configuration, and user request.
2. Exact request actually handed to the provider, including cache provenance.
3. Exact raw provider response and finish/usage metadata.
4. Parsed structured response handed to backend logic.
5. Reducer/persistence input and persisted state.
6. User/client/server-visible response.

Pin the relevant entity/run ID, request ID, event type, agent, model, deployed
revision, and timestamps. Prefer raw provider and persistence artifacts over
summaries. Preserve omissions and malformed fields; never repair evidence while
diagnosing it.

## Decision matrix

| First divergence | Route |
|---|---|
| Actual request uses the wrong agent, prompt, schema, or provider config | `/llm-first` |
| Raw response omits or violates the exact requested contract | `/llm-first` |
| Raw response satisfies the contract but parsing changes or drops it | `/backend-first` |
| Parsed input is correct but reduction, persistence, or projection is wrong | `/backend-first` |
| A fixed acceptable response behaves inconsistently behind the provider boundary | `/backend-first` |
| Evidence cannot locate the first divergence | `UNDER-INSTRUMENTED` |

When useful, replay the same acceptable raw response twice through the backend
with the project's SDK-faithful realistic response fake. This is a diagnostic
comparison, not permission to change the backend before classification.

## Verdict

Emit exactly one route label with the first divergent artifact:

- `ROOT CAUSE ROUTE: LLM`
- `ROOT CAUSE ROUTE: BACKEND`
- `ROOT CAUSE ROUTE: UNDER-INSTRUMENTED`

In direct diagnostic mode, execute only already-authorized steps of the selected
owner skill. Investigation alone does not authorize repairs; pause any repair
step that needs additional scope while continuing permitted diagnosis:

- LLM route: execute `/llm-first`.
- Backend route: execute `/backend-first`.
- Under-instrumented: report the missing artifact and continue authorized
  inspection, capture, or reversible diagnostic instrumentation. Keep prompt,
  schema, and backend semantics unchanged while locating the divergence, then
  rerun this diagnostic. Ask only when obtaining the particular artifact requires
  access, a production mutation, or work outside the existing authorization.
  Continue independent authorized work while that specific action is blocked.

In review-only mode, stop after the evidence-backed verdict and findings. Do
not launch owner skills, provider experiments, or edits.

## Protection review

Before accepting a backend guard, fallback, clamp, retry, sanitizer, or
suppression, classify it as one of:

- server-owned invariant;
- backend-transformation fix;
- prompt/schema-insufficient with raw-path proof;
- unproven fallback;
- model-ownership violation candidate (the ZFC workflow calls this a `ZFC violation candidate`).

Do not call backend protection necessary without server ownership or raw-path
proof. Retain any domain-specific approval gates from the active repository
policy.

## Guardrails

- Freeze the opposite side once a route is chosen.
- Do not edit prompt and backend behavior in one causal experiment.
- Do not add semantic keyword/regex routing, response repair, retry-until-pass,
  or hidden model-decision fallbacks.
- Synthetic fixtures prove deterministic behavior only.
- One real response proves capability, not statistical reliability.

