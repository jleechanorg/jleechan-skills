---
name: 4layer
description: /4layer - Four-Layer Minimal Repro Testing Protocol
---

Workflow type: testing. Execution mode: immediate.

## Purpose

Use this protocol to reproduce a blocker with the lowest sufficient evidence.
It owns `/4layer` and `four-layer`; command files dispatch to this protocol but
are not dependencies. Claude, Codex, and cloud sessions use the same workflow.

Before executing, read these mandatory companions completely, resolving them
relative to this skill (or by their exact registered names on catalog-only
runtimes):

- `../pr-blocker-min-repro/SKILL.md`
- `../integration-verification/SKILL.md`

If either companion is missing, report the dependency and do not claim the
workflow is complete.

## Runner discovery

Read the target repository's instructions and use its documented runner and
paths before executing. Do not assume a runner, fixture, credential, or
supported execution tool exists. Show the exact command and working directory;
examples in the companions are illustrative and do not authorize provider calls
or shared-state changes.

If a required runner, fixture, credential, or tool is unavailable, report
`UNSUPPORTED ENVIRONMENT / NO REPRO` with the checked paths. Unsupported is not
a pass and never justifies skipping an applicable layer.

## Minimal Repro Ladder

For applicable layers, run in this order and stop at the first layer that
conclusively reproduces the blocker. Move upward only after the current layer
passes; use the target repository's instructions and the testing-layers owner
(`../testing-layers/SKILL.md`) for the lowest sufficient claim boundary.

1. Unit
2. End-to-end
3. MCP/HTTP API
4. Browser

## Layer dispositions

In the final report, give every layer one disposition:

- `PASS`: executed and did not reproduce the blocker.
- `FAIL`: executed and reproduced the blocker; record the failure signature
  and identify the first conclusive reproduction.
- `UNSUPPORTED`: a required runner, fixture, credential, or tool is unavailable;
  report `UNSUPPORTED ENVIRONMENT / NO REPRO` and the checked paths. This is not
  a pass.
- `NOT RUN`: not executed; state why. For example, stop after a lower layer
  reproduces the blocker and mark each higher layer `NOT RUN`.

Do not omit a layer from the report or describe an unexecuted layer as passed.

## Execution Rules

1. Identify the blocker and target only relevant, minimal tests.
2. Require a fresh real failing run for the reported cause; old reports, traces,
   CI results, or observed symptoms are not causal RED proof.
3. Do not manufacture RED or use a paid real-model diagnostic loop; use the
   lowest sufficient deterministic layer before a live provider boundary.
4. Keep provider and user isolation so parallel runs do not collide.
5. Record absolute evidence paths after each executed layer.
6. Report the first conclusive reproduction and do not run unnecessary upper
   layers.
7. Inspection and packaging do not authorize provider calls, credential-file
   reads, shared-state mutations, or external publication.

## Evidence Requirements

After each executed layer, record the command, working directory, revision,
environment, duration, result, absolute evidence path, and failure signature.
Allocate evidence with `../scratch-space/SKILL.md`; do not hardcode a temporary
path; follow that owner's resolver and refusal rules. Correlate screenshots and
server logs to the same run where relevant, and redact secrets and private
content before authorized sharing.

Evidence must match the claim boundary: unit and end-to-end results establish
only deterministic claims, while MCP/HTTP or browser results establish only the
real service, provider, authentication, or UI behavior they actually exercise.
Record the final decision mapping the first reproducing layer to its component
class; layer classification is a triage hint, not root-cause proof.

## Integration claim gate

For an automatic integration claim, follow
`../integration-verification/SKILL.md` for configuration, trigger, and log
evidence. A manual test does not prove automatic activation. For a manual
integration claim, use the lowest sufficient real-service layer and report the
exact exercised scope.
