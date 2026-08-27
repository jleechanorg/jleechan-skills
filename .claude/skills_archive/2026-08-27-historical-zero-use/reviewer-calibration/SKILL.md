---
name: reviewer-calibration
description: "Run matched A/B reviewer calibration for /f: compare factory reviewer, raw codex exec, and delegated subagent reviews on the same frozen PR/work-item envelope."
---

# Reviewer Calibration

Use this skill when `/f`, `/factory`, or a PR/work-item review needs to prove
whether delegated reviewers miss blockers that raw `codex exec` catches.

## Controller-owned contract (current)

The default reviewer for every real run is the controller-owned cold review.
The controller v1 supports exactly one backend:

- **Codex only** — `codex exec --json --ephemeral --skip-git-repo-check` with
  the `--sandbox read-only` flag. The full prompt is sent on stdin (`-`).
  The reviewer cannot write the target; `--yolo`,
  `--dangerously-bypass-approvals-and-sandbox`, and any write-capable mode
  are explicitly rejected.
- Exit semantics: `0 = valid pass`, `2 = valid fail`, `1 = invalid / infra`.
  A valid fail must propagate as `2` and must NOT create panic artifacts.
- Inputs: `--base-sha` and `--head-sha` are required; `--workdir` must
  resolve to a non-symlink directory under the reviewed repo and must NOT
  point into the sealed holdout repo (`$DARK_FACTORY_HOLDOUTS`).
- `1 MiB` ceiling on `--task-file` and `--diff-file`.
- The Base64 envelope inside the prompt is **delimiter safety**, not prompt-
  injection isolation. The model still owns evidence sufficiency; the
  controller owns shape and digest invariants only.

Do not advertise a backend the controller cannot run. If a calibration lane
needs a different backend, route it through the raw terminal command
(`codex exec --yolo -m gpt-5.3-codex-spark …`) — it is the raw baseline,
not the controller contract.

## Rule

Calibration is default-on for real `/f` runs. Treat
`--reviewer-calibration=true` as present unless the user explicitly passes
`--reviewer-calibration=false` and gives a reason.

Do not claim one reviewer underperformed another unless both reviewed the same
frozen envelope at the same SHA with the same prompt.

## Frozen Envelope

Create `evidence/<run-id>/reviewer-calibration/envelope.json` with:

- `target_repo`
- `target_pr` or `work_item`
- `head_sha`
- `base_sha`
- `diff_path` or embedded diff hash
- PR body / task text snapshot
- evidence artifact paths and hashes
- test log paths and hashes
- factory `run_id`
- exact shared review prompt

## Reviewers

Run all available reviewers against the same envelope:

1. Factory/in-graph reviewer output, if the selected DOT has one.
2. Raw terminal mirror:

```bash
codex exec --yolo -m gpt-5.3-codex-spark \
  "Review this PR/evidence/diff. Blocker findings only. Use this exact envelope: <path>"
```

3. Delegated reviewer/subagent, when the current session supports subagents.

## Artifacts

Write:

```text
evidence/<run-id>/reviewer-calibration/
  envelope.json
  prompt.txt
  raw-codex.output.md
  raw-codex.findings.json
  subagent.output.md
  subagent.findings.json
  factory-reviewer.output.md
  factory-reviewer.findings.json
  comparison.json
  adjudication.md
```

If a reviewer is unavailable, write an output file explaining why and mark that
reviewer `unavailable` in `comparison.json`.

## Finding Schema

Each reviewer should return JSON plus free-form text:

```json
{
  "reviewer": "raw_codex|delegated_subagent|factory_parallel_reviewer",
  "target_head_sha": "...",
  "verdict": "blockers|no_blockers|inconclusive",
  "findings": [
    {
      "severity": "blocker|major|minor",
      "claim": "...",
      "file": "...",
      "line": 123,
      "evidence": "...",
      "repro_or_reason": "..."
    }
  ],
  "confidence": "high|medium|low"
}
```

## Adjudication

A finding is confirmed only if one of these is true:

- the user confirms it;
- the PR/work item changes to fix it;
- CI/test/review evidence later proves it;
- another independent reviewer confirms it with exact evidence.

Classify reviewer deltas:

- `confirmed_miss`: reviewer A missed a later-confirmed blocker found by reviewer B.
- `unconfirmed_delta`: reviewers disagree, but no ground truth exists yet.
- `false_positive`: reviewer claimed a blocker later disproven by evidence.

## Final /f Output

Include:

```text
Reviewer calibration: enabled <artifact-path>
Raw Codex verdict: <...>
Delegated reviewer verdict: <...>
Factory reviewer verdict: <...|unavailable>
Agreement: <yes|no|partial>
Confirmed gap: <pending|yes|no>
```

If disabled:

```text
Reviewer calibration: disabled <explicit reason>
```

