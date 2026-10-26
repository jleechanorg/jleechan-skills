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

- `.claude/skills/zfc-adjuster/SKILL.md`
- `.claude/skills/evidence-standards.md`
- `.claude/skills/zfc-leveling-roadmap/SKILL.md` for level-up/rewards changes

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
6. Validate the manifest with `scripts/adjustment_proof_matrix.py validate`.

One disabled worktree per adjustment is mandatory. A bundle named for one
adjustment cannot prove or delete another adjustment.

## Required Artifacts

Each green and red evidence directory must contain:

- `run.json`
- `metadata.json`
- real HTTP request/response capture, such as `http_request_responses.jsonl`
- real LLM capture, such as `llm_request_responses.jsonl`
- matching git SHA provenance for the worktree that produced the evidence
- checksums when the harness provides them

For LLM-interacting level-up/rewards paths, unit tests are supporting evidence
only. They cannot establish `proven` or `delete_candidate`.

## How To Run A Proof

Use the script to list registered adjustments:

```bash
./scripts/adjustment_proof_matrix.py list
```

Create a deterministic proof plan for one adjustment:

```bash
./scripts/adjustment_proof_matrix.py plan \
  --adjustment-id level_up_atomicity.suppress_unpaired_rewards_box \
  --test-command '<real testing_mcp invocation from the target repository owner>'
```

Create both independent worktrees with `diskm worktree-new` under
`~/.worktrees/<repo>/<name>`; the generated proof plan must point to those
approved Git worktree paths, never to `/tmp`. Keep evidence and captures in a
unique `/tmp/<repo>/evidence/<run-dir>/` directory. In the red worktree, disable
only the named adjustment. Prefer the narrowest possible edit:
remove or bypass the exact correction/suppression branch that implements the
registry entry. Do not change prompts, test harnesses, unrelated adjusters, or
scenario inputs in the red worktree.

After both runs finish, collect and validate:

```bash
./scripts/adjustment_proof_matrix.py collect \
  --adjustment-id level_up_atomicity.suppress_unpaired_rewards_box \
  --green-worktree ~/.worktrees/<repo>/<green-worktree> \
  --red-worktree ~/.worktrees/<repo>/<red-worktree> \
  --green-evidence /tmp/<repo>/evidence/<unique-run-dir>/green \
  --red-evidence /tmp/<repo>/evidence/<unique-run-dir>/red \
  --test-command '<real testing_mcp invocation from the target repository owner>'

./scripts/adjustment_proof_matrix.py validate \
  /tmp/<repo>/evidence/<unique-run-dir>/proof_manifest.json
```

The validator emits one of the allowed verdicts. Use that verdict in the PR body
or registry update; do not upgrade it manually.

## Review Rules

Fail the proof as `insufficient` when:

- the green or red bundle is missing `run.json` or `metadata.json`
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
