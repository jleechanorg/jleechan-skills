[Agent ask] Continue the work you were already assigned; this reminder adds a reconciliation pass, it does not replace, pause or
deprioritise your original task. Your current assignment and any operator request still outrank this reminder.

Do the reconciliation pass first, as a bounded check: it ends when you have confirmed whether any newer operator
request, cancellation or released hold changes your current assignment. If it changes nothing, return to the assignment
in this same turn and report the next step you executed. Only when a newer request genuinely supersedes the assignment
does the pass redirect your work, and then say which request and why.

If your task is blocked, do not loop on it. Report the blocker once as `UNBLOCK:` with its exact unblock condition.
After that, each turn must either execute an independent slice of the same task, or say
`IDLE: blocked <ground>, <unblock condition>` and stop. Say that at most once: repeat it only when the blocker's
evidence or its unblock condition actually changed, and say what changed. An unchanged blocker produces no message at
all, not a shorter one - silence is the correct output for a blocked task whose state has not moved. Re-probing the same
blocker, re-reading the same unchanged head, or re-stating the same unblock is not progress.

An independent slice means a remaining, authorized part of the same original assignment with a concrete deliverable you
can name before starting. If no such slice exists, say so in one line and stop - do not manufacture peripheral work to
look busy.

For the pass itself: check the last four hours of this conversation for new requests, changes and cancellations, and the
owner's authorized private roadmap and canonical backlog for older commitments that no live request supersedes.
Preserve task IDs, priorities, owners, checkpoints, approvals, holds and STOPs. Verify actual results and execution
timestamps; assignments and status claims are not progress. Report concise progress, precise blockers and next actions;
skip unchanged status.
