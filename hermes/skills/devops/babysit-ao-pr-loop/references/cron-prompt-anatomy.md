# Cron Prompt Anatomy — Babysit v1.3.0 Template

## Self-cancel contract reminder

Every babysit cron prompt MUST end with the v1.2.0 executable self-cancel clause:

```
After posting the Phase 0 terminal closeout, immediately call:
  cronjob action=remove job_id=$CRON_JOB_ID

Invoked as:
  python3 ~/.hermes/skills/ao-babysit/scripts/babysit.py poll \
      --session "$SESSION_ID" \
      --slack-channel "$CHANNEL" \
      --slack-thread-ts "$THREAD_TS" \
      --task-summary "$TASK_SUMMARY" \
      --cron-job-id "$CRON_JOB_ID"
```

Without `--cron-job-id`, the script cannot self-cancel and the cron leaks past terminal-state.

## Gate-detection copy (v1.3.0 — replaces any "awaiting skeptic verdict" wording)

**Forbidden phrases** (will never resolve now that Skeptic is deleted):
- ❌ "awaiting skeptic verdict"
- ❌ "waiting for /skeptic"
- ❌ "skeptic verdict (≤30 min cadence)"
- ❌ "skeptic-cron contract"

**Required phrasing** for the "still open, awaiting X" beat:

```
:hourglass: PR #<N> still open, awaiting:
  • CI rollups: Green Gate + Smoke Gate Wait (Gate 8) — currently <red|green>
  • Reviewers: CodeRabbit <state>, Bugbot <state>
  • Operator: MERGE APPROVED for the gh pr merge step

To stop or manage this job, send me a new message (e.g. "stop reminder PR<N> status (30m)").
```

## Full cron prompt template

```bash
hermes cron create "<schedule>" \
  --name 'PR<N> status (<interval>)' \
  --prompt "$(cat <<'EOF'
You are babysitting PR #<N> on jleechanorg/<repo>. Slack channel <CHANNEL>, thread_ts <THREAD_TS>.

On each tick, run the babysit-ao-pr-loop protocol. Specifically:

1. Phase 0 pre-flight: check `gh pr view <N> --json state,mergedAt` — if MERGED, post one closeout and self-cancel via `hermes cron remove $CRON_JOB_ID`. If CLOSED (not merged), post one escalation asking the operator.

2. Phase 1 observe: `git log`, `git status`, `ao session ls`, `gh pr view <N>`, and — only if worker has pushed since last tick — `gh pr

References:
- ~/.hermes/skills/devops/babysit-ao-pr-loop/SKILL.md (canonical)
- ~/.hermes/skills/devops/babysit-ao-pr-loop/references/post-skeptic-green-protocol.md (gate-detection recipe)
EOF
)" \
  --deliver 'slack:<CHANNEL>'
```

## Pitfalls

- **Re-using an old prompt verbatim.** v1.2.0 and earlier prompts template the "awaiting skeptic verdict" beat. Re-paste them as-is and the cron will quietly wait forever. Always rebuild from the template above when starting a new babysit.
- **`conclusion` vs `state`.** GitHub Actions populate `.conclusion`; `.state` is null for Actions and silently returns 0 failures when CI is red. Source: `~/.cursor/rules/env-preferences.mdc`.
- **Self-cancel requires `$CRON_JOB_ID`.** Inject it via `hermes cron create --prompt "...$CRON_JOB_ID..."` (or read it from `cronjob list` after creation) and forward to `babysit.py poll --cron-job-id "$CRON_JOB_ID"`. Without the flag, the script cannot issue `cronjob action=remove` on its own.
- **Smoke Gate failure is not a babysit concern.** If Gate 8 stays `failure` for >1 tick, post one root-cause hint and escalate to `drive-pr-to-green` / `finish-the-job` — do not loop indefinitely.