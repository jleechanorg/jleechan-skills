---
name: adjustment-proof
description: Use when proving, rejecting, or deleting backend adjustment registry entries with real LLM evidence and independent disabled-adjustment worktrees.
---

# Backend Adjustment Proof Protocol

## Purpose

Use this skill before accepting any claim that a backend adjustment is proven
necessary or safe to delete. A subagent report, PR prose, or one successful
organic run is not proof. Proof requires an isolated red/green comparator for
each adjustment.

This skill extends:

- [ZFC Adjuster](../zfc-adjuster/SKILL.md)
- [Evidence Standards](../evidence-standards/SKILL.md)
- Any ZFC proof or adjustment companion named by the active repository

## Verdicts

Allowed verdicts:

- `proven`: Current-head green evidence passes, and a separate worktree with
  exactly one adjustment disabled fails for the matching behavior.
- `delete_candidate`: Current-head green evidence passes, and a separate
  worktree with exactly one adjustment disabled also passes. This is not enough
  to delete by itself; it means the adjustment lacks positive necessity proof.
- `insufficient`: Required artifacts are missing, stale, non-real, not isolated,
  or do not demonstrate the claimed behavior.

Do not use `delete` from a single negative run. Deletion requires a separate
design decision after reviewing broader coverage, risk, and whether the code is
now redundant.

## Non-Negotiable Proof Shape

For each adjustment ID:

1. Start from the live PR HEAD or the exact SHA being reviewed.
2. Create one green worktree with the adjustment enabled and unchanged.
3. Create one red worktree with only that adjustment disabled.
4. Run the same real-server, real-LLM evidence command in both worktrees.
5. Save a manifest with:
   - adjustment ID
   - base SHA
   - green worktree path and evidence directory
   - red worktree path and evidence directory
   - the red worktree diff that disables the adjustment
   - exact commands used
   - raw evidence paths
6. Validate the manifest with the repository’s proof validator when specified.

One disabled worktree per adjustment is mandatory. A bundle named for one
adjustment cannot prove or delete another adjustment.

## Required Artifacts

Each green and red evidence directory must include these roles in the active
repository’s documented format (map the actual paths in the manifest):

- machine-readable scenario outcomes and error details
- capture provenance and run metadata
- real HTTP request/response capture, such as `http_request_responses.jsonl`
- real LLM capture, such as `llm_request_responses.jsonl`
- matching git SHA provenance for the worktree that produced the evidence
- checksums when the harness provides them

For paths whose claim depends on real model behavior, unit tests are supporting
evidence only. They cannot establish `proven` or `delete_candidate`.

## How To Run A Proof

Resolve the adjustment ID, approved proof command, worktree setup, and capture
format from the active repository. Create independent green and red worktrees
with its supported tooling. Allocate separate evidence directories; do not use an
incumbent's working tree or change unrelated code, prompts, or fixture inputs.

On red, disable only the implementation of the named adjustment. Use the same
authorized command and inputs on both sides. If the repository supplies a proof
planner, collector, or validator, use the verified local versions. Otherwise
record the required manifest and inspect the paired artifacts against this
protocol. Report missing capabilities without guessing a command or widening
permission to make provider calls.

## Review Rules

Fail the proof as `insufficient` when:

- either bundle lacks readable outcomes or capture provenance under the repository’s artifact contract
- the bundle has no real LLM capture
- the evidence SHA does not match the worktree SHA and staleness tolerance was
  not explicitly justified
- the red worktree diff is empty
- the red worktree diff disables more than the named adjustment
- the same red run is reused for multiple adjustments
- a red run passes but the report calls the adjustment `proven`
- a red run fails for harness setup, auth, server boot, missing classifier, or
  mock-mode contamination instead of the adjustment behavior

If red and green both pass, record `delete_candidate` and recommend either
deleting in a separate cleanup PR with broader evidence or keeping the registry
entry as runtime evidence missing until that cleanup decision is made.

## PR Body Language

Use precise wording:

- `proven`: "Disabling `<adjustment_id>` alone caused `<failure>` in red while
  the same command passed on green at `<sha>`."
- `delete_candidate`: "Disabling `<adjustment_id>` alone did not reproduce a
  failure under this proof command. This does not prove deletion is safe across
  all paths."
- `insufficient`: "Evidence did not isolate `<adjustment_id>` or lacked required
  real-LLM artifacts."

Never write "all blockers resolved" or "all adjustments proven" unless every
registered adjustment has its own validated manifest.
