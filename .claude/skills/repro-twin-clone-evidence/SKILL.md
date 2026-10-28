---
name: repro-twin-clone-evidence
description: Canonical /repro workflow for copy+targeted bug repro, twin clones, evidence exports, same-symptom verdicts, and red/green provenance.
---

# Repro evidence (canonical)

This `.claude` skill is the source of truth. Codex mirrors must point here rather than duplicating workflow rules.

## 0.5. Campaign ID extraction — do this first

**If the user pastes any URL matching `*/game/<id>` (e.g. `https://mvp-site-*.run.app/game/uZvPZPnBCVw3WtSEBWab`), extract `<id>` as the campaign ID immediately.** Go directly to §2 twin copy. Do NOT:
- Read the PR body or comments looking for a campaign ID
- Query Firestore indexes or list campaigns
- Use `get_campaign_state` before copying
- Ask the user what campaign they mean

The `/game/` path segment is the Firestore campaign ID. Take the first non-empty segment immediately after `/game/` and strip any `?`/`#` suffix (handles `/game/<id>/`, `/game/<id>?x=1`, `/game/<id>#frag`).

## 0. Routing

| User intent | Run |
|-------------|-----|
| `/repro`, `/repro <campaign_id>`, or "copy and reproduce this bug" | Default copy + targeted repro in section 2 |
| "first copy read-only, second copy gets actions" | Twin baseline + test subject in section 5 |
| "repro_copy", canonical+variant replay | copy to <your-email@example.com> (`--dest-email <your-email@example.com>`); `scripts/repro_copy_campaign.py` only when that exact workflow is requested |
| "five-class", "level-up suite", or all `test_level_up_class_*` | Heavy level-up suite only when explicitly requested |

Do not silently substitute a broader or easier harness for the requested repro.

## 1. Required environment

Use real services for evidence-bearing repros. Typical env:

```bash
export WORLDAI_DEV_MODE=true
export TESTING_AUTH_BYPASS=true
export ALLOW_TEST_AUTH_BYPASS=true
export MCP_TEST_MODE=real
export MOCK_SERVICES_MODE=false
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/serviceAccountKey.json"
export WORLDAI_GOOGLE_APPLICATION_CREDENTIALS="$HOME/serviceAccountKey.json"
```

For `<your-email@example.com>`, use `--dest-email <your-email@example.com>` — the UID is resolved automatically by `copy_campaign.py`.

## 2. Default: copy campaign + targeted bug repro

Goal: create a safe Firestore copy under the test user, then reproduce one reported bug with the narrowest faithful path.

1. Resolve source with `scripts/copy_campaign.py --find-by-id <CAMPAIGN_ID>`. Do not guess source UID.
2. Copy to the test user, usually `--dest-email <your-email@example.com>`.
3. For destructive replays, create two copies: read-only baseline and test subject.
4. Align the test subject to the reported bug instant without mutating the baseline.
5. Replay only the exact user action/input needed for the reported bug.
6. Export the test subject after replay with `scripts/download_campaign.py`.
7. Save raw request/response or streaming payloads and Firestore pre/post snapshots when the repro touches LLM/runtime state.

### 2.1 First-touch state proof for stale persisted-state bugs

When the bug is a stale persisted Firestore condition, orphaned session, legacy
flag, migration, cleanup, or routing loop:

1. Capture the copied campaign's pre-state with a direct Firestore document read
   before any app API call that could clean, migrate, normalize, or project state.
2. Do not call `get_campaign_state`, preview APIs, export endpoints, or UI loads
   before the evidence-bearing action unless the claim explicitly includes those
   first-touch paths.
3. Run the exact production ingress being validated (for gameplay, prefer
   `/api/campaigns/<id>/interaction/stream`) as the first app touch.
4. Capture post-state with another direct Firestore read.
5. Record selected agent/routing evidence when the claim is "not stuck on an
   agent" or "routes back to gameplay".

If a pre-action observer can mutate or seal the state, the evidence is only proof
that cleanup exists somewhere; it is not proof that the reported gameplay path is
fixed.

## 3. Red/green code provenance requirement

A red repro must not run against the candidate fix codepath. Before calling any run RED, record the code/environment provenance:

- RED replay: pre-fix checkout, pre-fix deployment, or explicitly human-approved origin-main red environment.
- GREEN replay: candidate fix checkout/deployment.
- Unknown remote deployment version is not valid RED evidence. Label it `AMBIGUOUS ENVIRONMENT` until the deployed SHA/config is proven or the human explicitly approves it as the red lane.
- If only the original production/source campaign artifact shows the failure, label it `HISTORICAL RED ARTIFACT`, not a fresh red replay.

Do not compare a fixed-branch replay against a fixed-branch replay and call the first one red.

## 4. Same-symptom requirement (fail closed)

Before running a repro, write the exact observable bug phenotype in concrete terms:

- Source campaign / URL and source account.
- Exact scene / turn / input being replayed.
- Exact user-visible symptom required for success.
- Prior artifact(s) that must be repeated, omitted, contradicted, or otherwise reproduced.
- Evidence that would falsify the repro claim.

Do not call a related internal signal a reproduction unless the same observable symptom appears in the copied/new run.

Examples:

- If the reported bug is "old scene text repeated", a successful repro must show visible repeated old narrative in the new copied campaign, with earlier source scene/doc IDs and matching text spans.
- A stale `action_resolution.player_input`, stale location, wrong planning block, or wrong narrative thread is only a related finding unless the reported user-visible repeated narrative also appears.
- If the new run produces fresh prose from stale context, label it `RELATED STALE-CONTEXT FAILURE`, not `ORIGINAL BUG REPRO`.
- If the new run has the right internal stale field but not the user-visible symptom, label it `NON-REPRO FOR ORIGINAL PHENOTYPE`.

For every claimed repro, add a verdict table:

| Original required symptom | New copied-run observation | Evidence file / doc ID | Verdict |
|---------------------------|----------------------------|------------------------|---------|
| | | | `REPRO` / `RELATED` / `NON-REPRO` |

Only `REPRO` satisfies `/repro`. `RELATED` and `NON-REPRO` are useful evidence, but they do not complete the repro task and must not be described as the original bug reproduced.

## 5. Twin baseline + test subject

When the first copy must stay read-only:

1. Create two independent copies with `scripts/copy_campaign.py --find-by-id <SOURCE>`.
2. Name one `baseline read-only` and one `test subject`.
3. Never send actions, god-mode edits, or destructive state changes to the baseline.
4. Perform alignment, deletes, state resets, and replay only on the test subject.
5. Export both only when comparison is needed; otherwise export the test subject plus raw evidence.

## 6. Save state after repro

Export the post-replay state and execution artifacts to a discoverable directory on the dedicated Scratch volume resolved dynamically via the canonical scratch skill [`~/.claude/skills/scratch-space/SKILL.md`](../scratch-space/SKILL.md) (`diskm scratch-new <repo-path> <purpose> --kind evidence` or `~/.claude/skills/scratch-space/scripts/scratch-dir.sh`):

Note: The inline subcommand below uses `copy_campaign.py` with `--format json` to perform an early-exit email-to-UID lookup (it exits immediately and does not perform a copy).

```bash
# Resolve canonical evidence directory via ~/.claude/skills/scratch-space/SKILL.md
EVIDENCE_DIR="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh "your-project.com/repro-exports/<slug>")"
# Or allocate a managed lease:
# EVIDENCE_DIR="$(diskm scratch-new <repo-path> repro-export --kind evidence)"

./venv/bin/python scripts/download_campaign.py \
  --uid "$(./venv/bin/python scripts/copy_campaign.py --dest-email <your-email@example.com> --format json 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin)['dest_uid'])")" \
  --campaign-id <TEST_CAMPAIGN_ID> \
  --output-dir "$EVIDENCE_DIR" \
  --format txt
```

Or, if you already know the resolved UID from the copy step output, pass it directly via `--uid <UID>` (or utilize a dedicated resolver script like `resolve_uid.py` in the future for clearer maintenance).

## 7. Checklist

| Step | Done? |
|------|-------|
| Source campaign resolved with `--find-by-id` | |
| Red/green provenance recorded | |
| Same-symptom criteria written before replay | |
| Baseline/test clone separation preserved | |
| Exact input/action replayed | |
| First-touch direct Firestore pre-state captured for stale persisted-state bugs | |
| Production ingress under test was the first app API touch | |
| Full campaign export saved | |
| Raw captures/snapshots saved | |
| Verdict table filled with `REPRO`, `RELATED`, or `NON-REPRO` | |
