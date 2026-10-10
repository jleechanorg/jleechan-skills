# Conflict resolution for PR #488

Base update: `origin/main` at `5de1f9242bdc7bd76bf891fc3b0d371a2f954608`.
Risk: Medium overall; high for the advice model validator and Dot profile launch path.

## `.claude/skills/advice/SKILL.md`

**Conflict type:** Model policy wording.

**Original conflict:** The PR listed the exact supported model IDs; main summarized this as “GPT 6 and 6.1 models only.”

**Resolution:** Kept main's command and full-permission wording and added the PR's exact catalog list, explicitly rejecting 5.6 and unknown IDs.

**Reasoning:** The executable validator uses a closed catalog. The human-facing instructions must state the same restriction.

## `.claude/skills/advice/scripts/run_primary_pair.py`

**Conflict type:** Model validation and reviewer-process behavior.

**Original conflict:** Main broadened validation to a `gpt-6` prefix and improved verdict parsing and timeout cleanup. The PR introduced a closed allowlist and an explicit lane model argument. Git also auto-merged duplicate validator and `--codex-model` definitions outside the textual markers.

**Resolution:** Kept main's verdict parser, timeout cleanup, environment override, CLI option, and receipt flow. Kept the PR's 2-second process-snapshot bound, exact allowlist (`gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol`, `gpt-6.1-sol`), and explicit lane argument; removed the duplicate definitions and moved validation before the lane barrier so direct invalid calls fail before waiting.

**Reasoning:** This preserves main's reviewer reliability changes while enforcing the PR's stated model boundary.

## `.claude/skills/history-search/SKILL.md`

**Conflict type:** Model policy wording.

**Original conflict:** The PR's Luna preference wording overlapped main's added GPT 6/6.1 restriction.

**Resolution:** Kept main's current model restriction.

**Reasoning:** It is the newer shared policy and does not weaken this PR's advice-specific closed allowlist.

## `.claude/skills/parallelize-to-ceiling/SKILL.md`

**Conflict type:** Fallback model routing policy.

**Original conflict:** The PR retained the `codex-luna` fallback; main changed fallback routing to the active GPT 6/6.1 tier and forbade 5.6.

**Resolution:** Kept main's current fallback policy.

**Reasoning:** This preserves the latest shared route and model invariant.

## `.claude/skills/swarm/SKILL.md`

**Conflict type:** Model policy wording.

**Original conflict:** Main added the 5.6 restriction to the same long routing instruction edited by the PR.

**Resolution:** Kept main's current wording, which includes the 5.6 restriction.

**Reasoning:** The current shared model policy remains intact.

## `tests/test_workflow_command_pairs.py`

**Conflict type:** Assertions for model routing text.

**Original conflict:** Main updated the expected fallback wording and added the model restriction; the PR expected the prior `codex-luna` wording.

**Resolution:** Kept main's current assertions, which match the updated shared skill.

**Reasoning:** The test must follow the current routing contract after the conflict resolution.

## `.claude/skills/dot/scripts/dot.sh`

**Conflict type:** Semantic overlap without textual markers.

**Original conflict:** Main removed the PR's configured subprofile selection and repeated profile validation before launching visible Chrome.

**Resolution:** Preserved the PR's profile validation and configured `--profile-directory` launch path.

**Reasoning:** Dropping these checks would undo the PR's dedicated-profile protection and could launch login into a different Chrome profile.
