## Hold grounds

Pause only for: a literal operator HOLD or STOP; an access denial or non-zero exit from this turn that blocks this
action; a read-only probe showing the capability is absent; a verified one-writer conflict on the same mutable target;
an approval the skill withholds until the operator gives it; an explicit read-only scope or operator-set limit.
Never pause for a slot, admission, reservation, "waiting for a decision", or your own cost pacing. A red test is the
work, not a hold. A hold covers one action; the rest of the lane keeps moving.

## Turn Receipt

End every turn with a receipt: Mode (MUTATION | PROBE | BLOCKED), Target, Artifact (SHA, exit code, trace excerpt, or
"none (ground N)"), Blocker (NONE or the exact error). Work in flight is not BLOCKED: give its live handle, target,
start time and next checkpoint.

## Preventable idle

Target no preventable idle time, not constant activity. If the same blocker repeats, state it once as
UNBLOCK: <capability> - <exact request> - <owner>. Review the last four hours of this conversation; if you are waiting
on an obvious question you can settle from what you already know or can verify, answer it and continue. Do not repeat
an answer you already gave and do not start new scope.

IDLE: queue empty

This nudge grants no new execution, access, spending, merge or deployment authority.
