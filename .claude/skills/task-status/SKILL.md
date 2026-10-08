---
name: task-status
description: Give frequent, evidence-based task progress updates in ChatGPT dot. Use for multi-step, delegated, long-running, resumed, or monitored work; requests for status, more frequent updates, or task states; and transitions involving waits, blockers, review, or completion. Keep trivial actions lightweight.
---

# Task status

Keep the user informed while doing the work. Report observable progress rather than activity theater. A skill supplies instructions, not a scheduler, background worker, new access, or authorization.

## Establish the task

Reuse the current task's scope and source of truth. Track only what is useful: task/outcome, acceptance criteria, owner, state, latest evidence and observation time, next action, and any dependency, next check, or resumption trigger. Keep this lightweight; do not create a new tracker or duplicate an existing one merely to report status.

For prior work, use available `/history` and `/ms` workflows or their supported equivalents: narrow the topic, date range, and sources; retrieve bounded relevant excerpts; retain provenance; verify mutable status against a current source. Distinguish no matches, unavailable sources, and unsearched sources. Treat historical permission as context, never current authorization. Do not probe denied locations or expose private records.

## Choose one state per task

- **Not started:** Accepted or queued, with no execution evidence. Name the owner or prerequisite and what starts the work. Delegation admitted is still queued until execution is observed.
- **Planning:** Actively resolving approach, scope, or dependencies. State the decision being settled and the next concrete action; do not remain here after execution starts.
- **Working:** Executing or verifying with current evidence. Mention the useful phase, such as implementation or testing. Evidence of a running process supports “running,” not “passed.”
- **Waiting on X:** Progress depends on an identified person, process, result, or event that has a credible path forward. Name X, the owner when known, and the next check or resumption trigger. Never promise monitoring that has not actually been established.
- **Blocked:** A specific obstacle prevents the next necessary step, and waiting alone has no established path to resolve it. Explain the effect and the smallest decision or action needed. Continue independent authorized work and give it its own state.
- **Ready for review:** The reviewable deliverable exists and the checks available within scope are complete or explicitly qualified, but requested human review or a decision remains. Provide the artifact, exact review request, and outstanding caveats. Do not use this state to shift ordinary verification to the user.
- **Finished:** The requested acceptance scope is met and verified, including delivery when required. State the result and decisive evidence. Finishing a draft is enough only when the user requested a draft; a PR being created is not a completed merge request.

Use **Paused** only for an explicit pause or a real execution suspension: say why, who or what can resume, and the trigger. Honor user pauses; do not silently restart them. Use **Canceled** for an explicitly canceled or superseded task. Failure is evidence to diagnose and recover from where authorized, not automatic cancellation. If execution is stale or unknown, say “last confirmed … at …; current state unverified” and obtain fresh evidence rather than inventing a transition.

Keep parent and child scope separate. “Authentication is blocked; the independent checks are working” is more accurate than labeling all work blocked. Partial completion is not whole-task completion. The coordinating assistant owns consolidated updates and must not assume worker messages reach the user.

## Update at a useful cadence

Send promptly on meaningful state changes, material findings, a blocker or decision, an unexpected delay, review readiness, and completion. For ongoing active work, default to a brief update around every five minutes unless the user specifies another cadence. Keep “for this one” overrides scoped to that task; do not turn them into a lasting default. Apply an explicit one-minute request during the active session when the available runtime supports it; do not silently replace it with five minutes.

Check evidence before each update. Keep a lightweight last-update time and next-check intent in the active task. Consolidate parallel work into one short message. If the user requested timed heartbeat updates, a truthful unchanged check is useful: state what was checked and what is still awaited. Otherwise avoid repeating the same message without new information. Do not manufacture progress, percentages, deadlines, or background activity to fill a cadence.

Use only available, verified timing and messaging tools. Distinguish an active-session check loop from a configured automation. Exact wall-clock delivery cannot be promised when the runtime cannot guarantee it. A long tool call can delay an active-session update; report that honestly. If the session ends, disconnects, or cannot schedule the requested cadence, disclose the limitation and the actual resumption trigger. Do not create an automation merely to finish an operation already underway. If a requested recurring schedule is unsupported or rejected, report that and ask before changing its cadence. Never claim a scheduled task exists until its creation and schedule are verified.

Send no more frequent updates after the requested outcome is complete, canceled, or paused, unless the user requested further monitoring. Do not stop outcome-based monitoring simply because several checks were unchanged; stop at the authorized outcome, user stop, relevant observation-window end, or a blocker requiring input. Never use status reporting to invent unrelated work.

## Ground every claim

Prefer direct results and artifacts over summaries. Distinguish sent, admitted, started, consumed, acknowledged, and completed when that distinction matters. A message being accepted does not show that the recipient acted on it. Read the resulting output before claiming its effect.

For tests, distinguish requested, running, passed, failed, skipped, and not run. Cite the observed run, revision, scope, result, and time when relevant; do not turn a worker's unverified claim into a verified pass. Re-check after material changes. If evidence is partial or old, state the gap. Do not describe a prepared file, attempted upload, or accepted send as verified delivery.

Keep permissions unchanged. Status reporting does not authorize new providers, paid calls, installs, access grants, external communications, or irreversible actions. Report an authorization blocker and continue unrelated authorized work. Do not add mandatory skill loading, reviews, trackers, or approval gates to trivial actions.

## Write the update

Use the user's channel and normal language. Lead with the result or state, then the next step or needed decision. One or two sentences usually suffice. Include evidence time when freshness matters and link the relevant artifact or source when available. Do not expose hidden reasoning, private notes, or implementation plumbing.

Useful pattern: “<Task>: <state>. <What changed or was checked>. Next: <action/owner/trigger>.” Omit redundant fields; this is a guide, not a required form.

Examples:
- “Tests are running on the latest revision. The unit suite passed; the integration result is still pending.”
- “Waiting on the export. It was accepted, but I haven't confirmed the output yet; I'll check again during this session.”
- “The sign-in step is blocked on your approval. I'm continuing the independent checks.”
- “The draft is ready for your review: [link]. Please check the proposed scope; publication is still pending.”
