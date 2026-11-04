---
name: cmux-goal
description: Set or verify an authorized session goal using a native goal API, with a verified cmux composer fallback only for a compatible Claude Code session.
---

# cmux-goal

Use when the user asks to set a session goal. Loading this skill does not set a
goal, create a persistent hook, authorize a mission, or communicate with an
outside agent. A goal's completion criteria cannot expand the task's access,
publication, spending, or other action permissions.

## Resolve the objective and existing state

Accept literal condition text, `from-bead <id>`, or `harden first: <goal>`.
For a referenced issue/bead/document, read its actual contents through an
authorized source; an unavailable tracker is a blocker to deriving criteria,
not permission to install it. Preserve the user's requested scope.

Consult relevant available prior conversation, task history, and repository
criteria when they change the goal. Do not invoke absent `/ms`, `/history`,
`ironclad`, test infrastructure, or local hooks merely because the source
workflow named them. This package is self-contained for goal formulation.

Query active goal state using the runtime's supported read API first. Keep an
existing matching goal. Do not clear or replace an existing different goal
unless the user explicitly requested that change. If no read API exists, use
only a documented compatible session command; `/goal active` is a retained
Claude Code source convention, not a universal goal API.

## Formulate verifiable exit criteria

Make the condition concise, binary where practical, tied to concrete evidence,
and bounded by the requested task. Prefer existing authoritative criteria and
checkers. If the user supplied a criteria document, preserve its exact scope
and make it accessible to the session before referencing it. A short goal can
point to a verified absolute document path where that runtime requires one;
do not create or rewrite a canonical document merely to satisfy this adapter.

Define required outputs, checks, relevant revision/artifact, and what blocked
dependencies mean. An unavailable external gate is a blocker to report, not a
license to loop forever or weaken completion criteria. Local test evidence
may aid diagnosis; it does not satisfy a required remote CI gate unless the
user or authoritative project contract explicitly makes them equivalent.

## Choose the mechanism

Prefer a native goal API when the active runtime exposes one and verify its
persisted state. Do not infer native goal availability from a tool name in
another runtime, and do not call a progress-plan tool a Stop-hook goal.

For the cmux composer fallback, read
[cmux-steer](../cmux-steer/SKILL.md) and its
[submission contract](../cmux-steer/references/submission-contract.md).
Verify the installed target is a compatible Claude Code session with the
documented builtin. The source claimed a session-scoped Stop hook and purple
indicator; their existence and behavior must be verified on that build.

```bash
cmux identify --json
# Resolve only caller.workspace_ref and caller.surface_ref for self-targeting.
cmux tree --all --workspace "$WS_REF"
# TEXT is the approved literal /goal command, passed as one argument.
cmux send --workspace "$WS_REF" --surface "$SURFACE_REF" "$TEXT"
cmux send-key --workspace "$WS_REF" --surface "$SURFACE_REF" enter
```

Use `TEXT` equal to `/goal <condition>` only after inspecting the current
input state. If `caller` is null, self-targeting is not established; never
substitute the globally focused surface. A user-named different session must
be resolved explicitly, and external-agent communication approval must cover
that named agent and goal-setting action.

Do not inject a builtin into a shell, active generation, unrelated queued
prompt, approval dialog, or existing composer draft. If self-submission must
wait until the session is idle, use an available safe runtime route or provide
the exact command for the user. Do not schedule hidden self-keystrokes,
install hooks, interrupt work, or clear draft input as a fallback.

## Verify and continue

Query persisted goal state directly after creation and check the exact
condition and session. A runtime confirmation such as “Goal set” or a verified
session-scoped hook can support the result. `OK surface:N`, typed input, UI
color, or a processing label alone does not prove the goal was installed.

Use only the bounded retry in the submission contract if Enter demonstrably
did not submit. Do not recreate a matching goal or replace it to resolve an
uncertain response. Report `active`, `already matching`, or `not verified`
with the observed evidence. If setup is blocked, provide the usable command
or warning and continue any independently authorized mission work; never
claim the goal is enforced. `/goal clear` is outside ordinary goal setup.
