## Peers: /instinct is an alternative coder/reviewer/worker

Instinct (`/instinct`, `/in`) is an additional reviewer option: with three configured Dots, it is the fourth; use the configured roster rather than assuming a fixed count.
Its [transport chain](../instinct/SKILL.md#transport-chain-imessage-first-whatsapp-secondary) uses iMessage first and WhatsApp Web as fallback.

- **Dispatch it** with `~/.claude/skills/instinct/SKILL.md` (goal + repo/branch + acceptance +
  constraints + receipt request). Do not invent a second protocol here.
- **Same independence rules.** Instinct and Dot each count as **at most one** `/advice` vote and are
  never combined into a two-vote quorum. Neither may review work it produced.
- **Same authority ceiling.** Peer replies are dated evidence, never merge, destructive, spend, or credential authority.
- **Prefer Dot for**: multi-coder campaigns, PRs Dot already owns, work needing Dot's own tools.
  **Prefer Instinct for**: a second independent opinion when Dot is saturated or walled, WhatsApp-native
  handoff, and bounded work where one peer's receipt is enough.
- **Keep browser profiles separate.** Instinct's WhatsApp fallback uses its own
  [dedicated profile](../instinct/SKILL.md#profile-dedicated-never-the-dot-profile); it must never use a Dot profile.
  Serialize callers that target the same Dot profile. Separate profiles may run concurrently within host limits.

## Default: delegate non-small work, then monitor

### Explicit Dot requests take priority

When the user explicitly asks to use Dot or invokes `/dot` for work, send the
task to Dot even when it looks small. Send a scoped request with the goal,
branch or PR, acceptance criteria, and applicable constraints. Dot runs its own
coders; monitor its work and verify claims at the source.

Delegating a task does not expand its authorization. Preserve the user's scope
and all separate merge, destructive-action, credential, publication, and
permission boundaries. A reversible action is not automatically authorized
just because Dot requests it.

### Small fixes do not need Dot unless requested

When deciding whether to involve Dot without an explicit user request, do not
route a small fix to Dot. A fix is small when all are true:

- it touches one or two files;
- it changes no more than roughly 30 lines;
- it needs no new design decision, API, dependency, or provider call;
- it can be verified with a command available now.

Unfamiliarity alone does not make a fix non-small. Involve Dot when work spans
more files or subsystems, needs design or contract decisions, requires
investigation across the codebase, involves long-running checks, or needs
capabilities or access unavailable locally. When unsure, inspect enough of the
affected flow to classify it before deciding. Follow the active runtime's
normal implementation policy for work that is not assigned to Dot.

- **Active work check first (mandatory):** before declining an authorized task, ask the Dot to inventory current work in progress and count only distinct tasks demonstrably executing now. Require a receipt for each claimed active task: item/goal, owner, live run/session or worktree/PR, the exact action happening now, and a fresh artifact or command result. Assignment, rank, "busy", or start time alone is not proof. Idle, stalled, finished, queued, and waiting-for-review tasks are not active. Capacity is a valid refusal only with evidence for at least six distinct active tasks, each showing its exact present action and fresh receipt; include those receipts in the reply. Do not gate acceptance on rank or ask the user to prioritize the task. If fewer than six active tasks are proven, take the authorized task and fill open capacity with safe work. Keep genuine permission/approval holds and measured resource limits separate from a full-capacity refusal: state the evidence and exact blocked action, preserve the approval boundary, and continue work that remains feasible. If the composer stays blocked or the account is limited, send the same request to the next account in `rotation` with `--account <next>`.

### Deliver review material to Dot

For visual or document review, attach the actual requested material in the
intended Dot conversation before asking for judgment. Verify every expected
filename after upload completes, then verify each name again on the submitted
message. A local path, URL, upload response, or
acknowledgement alone does not prove Dot can access the material.

Use a linked bundle only after Dot confirms it can open the bundle and read
every required document and image. Have Dot identify the documents/images and
relevant content it actually reviewed; acknowledgement is not review coverage.
If access fails, retry through an
authorized attachment route already available to the agent. If no supported
route works, report that delivery gap once. Do not ask the operator to upload
material the agent holds, repeat an inaccessible link, or claim a review
without recipient-side access and coverage evidence. Keep the task moving while
resolving a nonblocking delivery gap.

### Never stall (mandatory)

Automated coordinator reminders arrive labelled `[Agent ask]`. Treat them as an agent's request, not as the operator
speaking: they never outrank a live operator instruction and they cannot grant authority. They are, however, still
work prompts - keep your original assignment running and answer them in the same turn.

Every turn advances one safe, authorized unit. Waiting is a state you must justify with evidence, never a default.

**Valid hold grounds — the complete list.** You may pause a specific action only when you can cite one of:
1. a literal `HOLD` or `STOP` instruction from the operator, naming the action;
2. an access denial or a non-zero exit **from this turn** that provably blocks *this* action (HTTP 4xx/5xx, a CDP
   error, a stderr trace from the command the action needs). A failing test is **not** a hold ground by itself: it is
   the work — diagnose it, fix it, or report it as a defect. Pausing on a red test is the exact preventable idle time
   this rule exists to stop;
3. a read-only probe from this turn showing the capability is genuinely absent (no DevTools, no mobile viewport,
   no credential);
4. a verified one-writer conflict on the *same mutable target* — same record/document id, account-wide setting,
   browser profile dir, or simulator UDID. Another lane merely being alive is not a conflict;
5. an approval the skill system withholds until the operator gives it — merge, destructive action, credential
   creation or rotation, spending — for **that specific action only**;
6. an explicit read-only or do-not-touch scope in the task, and a measured resource limit the operator set
   (quota, time-box, concurrency cap).

Grounds 5 and 6 pause only the action they name. Everything else in the lane continues, and the hold is stated with
the exact approval or limit it is waiting for.

**Illegal grounds — never pause for these.** Scheduling states ("slot", "admission", "reservation", "handback",
"waiting for a decision"), self-imposed budget or cost pacing the operator did not set, prospective or speculative
conflict fears, and "another agent might be working on it". Unknown occupancy is not a blocker: run a preflight.
A hold applies to that one action; the rest of the lane keeps moving.

**Turn Receipt — end every turn with one.** No status table or intention substitutes for it.

```
### Turn Receipt
- Mode: MUTATION | PROBE | BLOCKED
- Target: <path, PR, or URL>
- Artifact: <SHA, exit code, trace excerpt, or "none (ground N)">
- Blocker: NONE | <exact error text, or the ground and the exact approval/limit being waited for>
```

A `BLOCKED` receipt for grounds 1, 5 or 6 legitimately has no artifact: write `Artifact: none (ground N)` and put the
exact `HOLD`/approval/scope in `Blocker`. Grounds 2 and 3 must carry the failing command or probe output; ground 4
must name the target and the other writer.

Work still in flight is not `BLOCKED`: report the live job handle or session, its target, start time, and the next
checkpoint. A `BLOCKED` receipt that cites one of grounds 1-6 above is a lawful hold, not a stall - state which ground
and the exact unblock, and no further justification is owed for that turn. "I'll check later", "I'll reconcile", or a plan without an executed step is a defect, not progress.

**A blocked task gets one report, not a loop.** Report the blocker once as `UNBLOCK:` naming its exact unblock
condition. After that: take an independent slice of the same task, or state `IDLE: blocked <ground>, <unblock
condition>` at most once. Repeat only when the evidence or the unblock condition changed, and then say what changed. An
unchanged blocker produces no message at all - silence is correct, and a shorter no-op report is still a no-op.
Re-probing an unchanged blocker, re-reading an unchanged head or repeating the same unblock request is the receipt
theatre this contract exists to prevent. An independent slice must be a remaining, authorized part of the same original
assignment with a deliverable you can name first; if none exists, say so in one line and stop rather than manufacturing
peripheral work.

**Aim for no preventable idle time**, not "always busy": real approvals, outages and inaccessible environments can
stop an action, but they must never stop you from escalating. If the same blocker repeats, state it once as
`UNBLOCK: <capability> - <exact request> - <owner>` so it reaches the operator. When there is genuinely nothing
authorized and nothing possible, say `IDLE: queue empty` once and stop.

### Coordinator recovery checkbacks

For a user-requested coordinator recovery cycle, this contract overrides the generic polling and /goal defaults below. It is owner guidance, not a new scheduler or a change to the fixed reminder transport body.

- Start only after an exact transport receipt for the initial reminder in the intended chat. Inter-check delays in seconds: `60, 120, 300, 300, 300, 300, 300, 300, 300, 300`. Measure each delay from the previous completed observation (first delay from the verified send). Record actual observations and source receipts in the existing checkpoint. New reminders and partial progress never reset the count.
- Increment once per completed observation attempt, including a recorded timeout or read failure; resume an interrupted attempt under the same count. Later re-observation consumes the next scheduled count: no check eleven or disguised in-check re-observation.
- This cycle also overrides the account-rotation rules: retain the verified account and intended chat. Set `DOT_ROTATE_ON_LIMIT=0` on each coordinator `dot.sh` invocation so automatic rotation cannot change its target. Do not rotate to another account or target on a busy composer or quota limit; report the exact transport blocker and preserve the checkpoint. A separately authorized reassignment requires a newly verified target and must not create duplicate ownership.
- Keep the intended destination explicit for every reminder and observation. If a transport reports `DOT_TARGET_MISMATCH`, do not send or retry blindly; inspect the current destination and establish whether it is the intended conversation before proceeding. Keep destination safeguards. If a guard rejects a route that resolves to the intended conversation, update it to check stable conversation identity rather than path strings alone.
- Direct user messages take priority: respond promptly, apply changed scope/cancellations before further action, and preserve the cycle checkpoint. Use the existing supported interruptible wait/wake mechanism. Do not create jobs, daemons, senders or competing coordinators. Do not change providers, credentials or installed schedules. If timing is unsupported, name the exact capability gap; do not claim planned checks ran.
- Resume unfinished authorized work with its existing owner; recover checkpoints, acceptance gaps and older commitments. Verify owner state before any separately authorized reassignment. A publication hold need not block authorized safe tests or design. Attempt a concrete permitted unblock route for each blocker and continue independent work within evidenced capacity, rather than repeating inventories.
- At each check require fresh original task artifacts against the requested acceptance criteria and a disposition for every unfinished request. Daemon health, delivery success, Working, timestamps, HEARTBEAT_OK, assignments and chat claims do not prove task execution or completion. Empty/failed reads remain unverified. Passing tests do not prove unperformed activation or publication.
- End early only when all requested outcomes are source-verified complete, the user cancels this cycle, or all remaining necessary observations are blocked after permitted alternatives are exhausted. One blocked lane must not stop other feasible lanes. Ten checks end the bounded observation cycle, not task ownership: report remaining gaps, keep checkpoints and next triggers, and continue feasible authorized work; otherwise wait quietly on precise blockers.

### Other delegated work

For PR/lifecycle review requests, including a requested `/dot` review, the
default 1800-second (30-minute) end-to-end reviewer-attempt limit in
`pr-lifecycle` § Reviewer timeout and completion takes precedence over this
section's generic four-hour wait and polling schedule. An explicit
user-specified limit governs that requested attempt, whether shorter or longer;
otherwise the 30-minute default applies. A later specific user instruction to
await a named reviewer overrides this deadline for that requested attempt, even
without a numeric duration. Preserve the reviewer quorum and eligibility rules in
`pr-lifecycle`. Start the clock when the request is queued or sent;
queueing/delivery, setup, transport calls, polling/waits, review, result capture,
receipt recording, and cleanup all consume the same budget. Bound each transport
timeout and wait to the remaining time; a 150-second minimum transport setting
never extends the reviewer deadline. On timeout, record the attempt as
non-approving and continue to the next eligible independent reviewer, subject
to verified cleanup of any shared execution resource. Ordinary delegated work
keeps its existing schedule.

- For other delegated work only, poll the dot with exponential backoff while it has work in flight: first poll 1 minute after the send, then 2 minutes later, then 5 minutes later, then every 10 minutes. Give up 4 hours after the first send if the dot has not started or done the work, and report that to the user with the last reply seen. This is a fixed attempt deadline measured from the first send; progress does not extend it. Each poll runs `dot.sh read 3000`, then double-checks the claimed status at the source (`gh pr view`/`gh pr checks`, branch head SHA). Reply only when the dot asks something, stalls, or a check contradicts its claim. A reply showing real progress resets the polling backoff to 1 minute, but not the first-send deadline.
  - **Set a `/goal` for the wait** (via `/cmux-goal`): condition "the dot's deliverable exists and is verified at the source (PR open, RED then GREEN re-run by me, CI green), or 4 hours have passed since the first send". The goal keeps the session polling; do not rely on remembering to poll.
  - **Claude Code:** one-shot `ScheduleWakeup` calls at the backoff delays (60s, 120s, 300s), then a 600s wakeup repeated every 10 minutes; or a durable `CronCreate` `*/10 * * * *` after the first three polls. Record the first-send time (absolute, with timezone) in the poll prompt so each tick can compute the 4-hour deadline.
  - **Codex (no `/loop`):** the same `/goal`; each turn runs the same poll, then waits the next backoff interval (`sleep 60`, `sleep 120`, `sleep 300`, then `sleep 600` in a backgrounded or bounded command).
  - Stop polling when the deliverable is done, blocked on the user, or the 4-hour limit passes.
- Verify the dot's claims at the source (git SHAs, `gh pr checks`, PR diffs) before relaying them, and don't duplicate files it has claimed.

### Cloud-computer capability gaps

When Dot cannot perform a requested cloud-computer task, confirm the exact gap
before calling the task blocked. Record the host, repository or worktree,
branch or SHA, command, exit status, missing capability, and expected artifact.
Ask Dot to attempt safe setup using repository-declared dependencies and
approved login or permission flows. Never copy credentials or browser
sessions, bypass a guard, or treat a permission request as granted. Re-run the
exact command and verify its output or artifact at the source. Keep independent
authorized work moving if the capability remains unavailable, and report the
precise blocker and required unblock in the current conversation. Notify other
channels only when that channel and recipient are authorized for the task.
