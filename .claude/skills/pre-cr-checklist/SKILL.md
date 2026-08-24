---
name: pre-cr-checklist
description: Pre-CR self-review checklist — run before promoting a PR from Draft → Ready (before first CodeRabbit review)
---

# Pre-CR Self-Review Checklist

Run this before promoting a PR from Draft → Ready (before first CodeRabbit review).
Each item checked here prevents one ~4-commit CR fix+evidence cycle.

## Level-up / rewards / XP changes

- [ ] All `_project_level_up_ui_locally` call sites pass `original_state_dict=` explicitly
- [ ] No raw-truthy on Firestore level-up flags — use `_is_state_flag_true()` / `_is_state_flag_false()`
- [ ] Contradiction guard present: if XP < threshold, `level_up_available` forced False
- [ ] `_sync_level_up_signals` clears `rewards_box_lua` when `level_up_detected=False`
- [ ] Malformed true signals (missing `new_level`, wrong XP totals) handled fail-closed
- [ ] Every path that writes `rewards_box` to Firestore calls `normalize_rewards_box_for_ui()` first

## Evidence completeness (before promoting from Draft)

- [ ] Terminal recording: `.cast` + `.gif` + `.mp4` present in `docs/evidence/pr-NNNN/terminal_recording/`
- [ ] Browser video: `.gif` + `.mp4` present if any UI-visible behavior changed
- [ ] `docs/evidence/pr-NNNN/claim_artifact_map.md` exists with overall verdict
- [ ] PR body contains evidence links (gist URL or `docs/evidence/` path)
- [ ] `/es NNNN` passes locally before first push as non-draft

## General

- [ ] No `try/except` around imports; no inline imports inside functions
- [ ] No new env vars (use constants.py instead)
- [ ] `shell=False, timeout=30` on all subprocess calls
- [ ] Net production LOC check if this is a deletion/cleanup milestone
