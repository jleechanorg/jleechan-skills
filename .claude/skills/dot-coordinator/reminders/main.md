[Agent ask] Continue the work you were already assigned; this reminder adds a reconciliation pass, it does not replace, pause or
deprioritise your original task. Your current assignment and any operator request still outrank this reminder.

Do the reconciliation pass first, as a bounded check: it ends when you have confirmed whether any newer operator
request, cancellation or released hold changes your current assignment. If it changes nothing, return to the assignment
in this same turn and report the next step you executed. Only when a newer request genuinely supersedes the assignment
does the pass redirect your work, and then say which request and why.

If your task is blocked, do not loop on it. A blocker may be reported once as `UNBLOCK:`; after that, each turn must
either execute an independent slice of the task that the blocker does not touch, or say
`IDLE: blocked <ground>, awaiting owner decision` and stop. Re-probing the same blocker, re-reading the same unchanged
head, or re-stating the same unblock is not progress and must not appear twice.

For the pass itself: check the last four hours of this conversation for new requests, changes and cancellations, and the
owner's authorized private roadmap and canonical backlog for older commitments that no live request supersedes.
Preserve task IDs, priorities, owners, checkpoints, approvals, holds and STOPs. Verify actual results and execution
timestamps; assignments and status claims are not progress. Report concise progress, precise blockers and next actions;
skip unchanged status.
