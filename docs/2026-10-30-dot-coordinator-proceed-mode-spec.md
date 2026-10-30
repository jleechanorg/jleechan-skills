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
5. On the host, activation retires the old `ai.gemini.agy-dot-coordinator.*` labels, loads nine
   `ai.dot-coordinator.*` labels (3 hourly main + 6 proceed), and a real scheduled proceed run
   completes with its declared mode.

## User story

Today the Dot can sit on a question only the coordinator can prompt it past, or idle after a
finished step, until the next hourly reminder. After this change, at :01/:02/:20/:21/:22/:40/:41/:42
the owning account's coordinator turn reads the last 20 messages and either answers what is
obvious, names the single owner decision required, or tells the Dot to proceed. Before: up to 60
minutes of avoidable idle. After: at most ~20 minutes, with no extra authority.

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
  Nine runs per hour across three accounts is three times the previous launch rate. Mitigation:
  cadence is data (`proceed_minutes`), staggered to keep one launch at a time, and documented in
  RENDERING.md.
- **Duplication.** More frequent turns mean more chances to repeat an answer; the fixed text
  forbids repeating an answer already given and unchanged status.
- **Authority creep.** A nudge that "answers questions" could drift into answering owner-only
  decisions; the text requires naming the single owner decision instead, and keeps the no-new-
  authority sentence.
- **Silent config drift.** Rendered minutes must stay disjoint because label/log names derive from
  the minute; the renderer now refuses overlap instead of merging two runs.
