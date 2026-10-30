# Dot coordinator: 20-minute `proceed` nudge mode

Date: 2026-10-30
Status: implemented; inactive-render reviewed, live activation recorded in the PR evidence.

## Outcome

One coordinator turn can now run in one of two declared modes:

- `main` (unchanged, hourly per account) sends the four-hour periodic reminder.
- `proceed` (new, every 20 minutes per account) reads the last 20 rendered messages of that Dot
  chat, settles an obvious pending question from authorized context, and otherwise tells the Dot
  to continue the next authorized step.

The machine-local schedule stays the single source of cadence: each account keeps its hourly
`minute` and gains a `proceed_minutes` array. Rendered runs carry `COORDINATOR_MODE` and, for
proceed, a leading `Coordination mode: proceed.` directive in `COORDINATOR_TASK`, so the agent
never has to infer its mode.

## Non-goals

- No change to transport, identity binding, destination verification, one-send limit, or the
  absence of durable holds/attempt receipts.
- No new authority: a proceed nudge cannot grant execution, access, spending, merge or deploy
  authority, and cannot answer a question that needs the owner's decision.
- No task ledger, no per-Dot state, no message queue, no retry/backoff ladder.
- No change to the shared capacity policy (2 complex + 2 short) or to the main payload selection.

## Acceptance

1. `render_native_schedule.py` renders `1 + len(proceed_minutes)` runs per account with distinct
   unit names/labels/log paths, `COORDINATOR_MODE` set, and the proceed directive present only on
   proceed runs.
2. Overlapping, duplicated, out-of-range or non-integer `proceed_minutes` are refused before any
   output directory is created.
3. `SKILL.md` declares both modes, states that mode is never inferred, and fixes the exact proceed
   outbound text plus its private override file `~/.config/dot/proceed-reminder.txt`.
4. Existing contracts still pass: exact main fallback text, one blockquote per mode section,
   launcher glue LOC budget (150), `dot-coordinator/SKILL.md` budget (400).
5. On the host, activation retires the old `ai.gemini.agy-dot-coordinator.*` labels, loads twelve
   `ai.dot-coordinator.*` labels (3 hourly main + 9 proceed, three nudges per account per hour), and
   a real scheduled proceed run completes with its declared mode.

## User story

Today the Dot can sit on a question only the coordinator can prompt it past, or idle after a
finished step, until the next hourly reminder. After this change, at :01/:02/:20/:21/:22/:40/:41/:42
the owning account's coordinator turn reads the last 20 messages to verify the destination and check
for a duplicate or peer draft, then sends the fixed nudge asking the Dot to settle what is obvious,
name the single owner decision it needs, or proceed. Before: up to 60 minutes of avoidable idle.
After: at most ~20 minutes, with no extra authority and no free text from the sender.

## Proof plan

- Offline: `python3 -m unittest tests.test_dot_schedule_renderer tests.test_dot_recovery_prompt`,
  the dot-coordinator compliance/timeout entrypoints, and `bash .claude/skills/dot/scripts/check_budget.sh`.
- Render: inactive staging directory with `plutil -lint` on every plist, then a table read back of
  label/minute/account/mode/binary.
- Runtime: `launchctl list` before/after activation, `launchctl print` per label, and the log of a
  real scheduled proceed run showing the declared mode was honored.

## Mock

Exempt: no UI. The change is a skill contract plus a schedule renderer; the only visual surface is
terminal/plist inspection, covered by the runtime logs above.

## Risk

- **Cost/frequency.** Each proceed run is a full Chrome profile launch plus one cheap-model turn.
  The operator-selected cadence is three nudges per account per hour, so twelve runs per hour across
  three accounts (four times the earlier one-message-per-hour rate). Mitigation: cadence is data
  (`proceed_minutes`), staggered so one account's own runs stay 15 minutes apart - longer than the
  720-second default deadline, so a slow run cannot collide with its own next launch - and documented
  in RENDERING.md. Different accounts still overlap, so the real bound is up to three concurrent
  launches on three separate profiles.
- **Sender free text.** "Settle the obvious question" is an instruction to the *receiving Dot*; the
  sender stays transport-only and never answers, chooses work or writes status. The sender reads
  messages for destination, duplicate and peer-draft verification only.
- **Duplication.** More frequent turns mean more chances to repeat an answer; the fixed text
  forbids repeating an answer already given and unchanged status.
- **Authority creep.** A nudge that asks the Dot to "settle an obvious question" could tempt the
  sender to answer on the owner's behalf; SKILL.md states the message asks the receiving Dot, the
  sender writes no analysis, and the text keeps the no-new-authority sentence plus an explicit
  "name the single owner decision you need" branch.
- **Silent config drift.** Rendered minutes must stay disjoint because label/log names derive from
  the minute; the renderer now refuses overlap instead of merging two runs.
