---
name: goalexec
description: Define a goal with success criteria and run autonomous convergence loop until criteria are met
---

# /goalexec Skill

Define a goal with measurable success criteria and run an autonomous convergence loop (plan→execute→validate→decide) until success criteria are met or convergence limits are reached.

## Usage

```
/goalexec "Fix the rewards latency issue"           # define + start immediate loop
/goalexec "Fix rewards" --cron 30m              # define + schedule recurring loop
/goalexec --validate                               # check status, no loop
/goalexec --current                               # show active goal + criteria
/goalexec --clear                                 # clear active goal
```

## Mode Parsing

Parse arguments to determine mode:
- Positional arg with text → primary mode (define + loop)
- `--cron <duration>` → scheduled mode (recurring loop)
- `--validate` → validation only
- `--current` → display only
- `--clear` → cleanup only

## Environment Detection

**CRITICAL: /goalexec must detect which agent runtime it's in and use the native looping mechanism.**

Three tiers, tried in order:

| Tier | Condition | Mechanism | Works in |
|------|-----------|-----------|----------|
| 1 | `CronCreate` tool available | `/loop <duration> /goalexec --validate` or `CronCreate` | Claude Code |
| 2 | cmux running (socket exists at `/tmp/cmux*.sock`) | `scripts/goalexec-loop-cmux.sh --install` (launchd + cmux reinjection) | Any agent in cmux (opencode, claude, etc.) |
| 3 | No CronCreate, no cmux | `scripts/goalexec-loop.sh --goal "..."` (bash while-loop + CLI) | Any terminal |

Detection logic:
1. If you have the `CronCreate` tool → Tier 1 (Claude Code native)
2. If `/tmp/cmux-debug*.sock` or `/tmp/cmux.sock` exists → Tier 2 (cmux reinjection)
3. Otherwise → Tier 3 (bash CLI loop)

## Primary Mode: Define + Loop

1. **Parse goal statement** from arguments
2. **Extract success criteria** — derive measurable, testable criteria:
   - "Create X" → "X exists with correct content"
   - "Fix Y" → "Y no longer fails"
   - "PR merged" → "PR state = MERGED"
   - "All tests pass" → "Test exit code = 0"
3. **Ensure `goals/` directory exists** (`mkdir -p goals/`)
4. **Check for existing goal** — if `goals/.current-goal` exists, warn and ask before overwriting
5. **Save goal to `goals/.current-goal`** (flat file, single active goal):
   ```
   # Goal
   <original statement>

   ## Success Criteria
   1. <criterion>
   2. <criterion>
   ...

   ## Session State
   - Iteration: 0
   - Last score: 0%
   - Status: DEFINED
   ```
6. **Announce criteria** — display them clearly
7. **Start convergence loop** — using the detected environment's native mechanism

## Convergence Loop

For immediate mode, run iterative cycle:
1. **Plan** → create actionable steps directly (no approval gate — autonomous mode)
2. **Execute** → run each step using appropriate tools/commands
3. **Validate** → check success criteria against reality
4. **Decide** → continue if improving, stop if converged/stalled/max-iterations

### Score Calculation

score = (met criteria / total criteria) × 100

A criterion is "met" if its validation check passes (file exists with correct content, test exit code = 0, PR state = MERGED, etc.).

### Convergence Decision Logic (priority order)

1. **100% criteria met** → CONVERGED, stop
2. **Max iterations reached** (default: 10) → stop with partial progress
3. **Same score 2 iterations** → STALLED, stop (checked before "good enough")
4. **≥90% + no progress 2x** → "good enough", stop
5. **Improving** → continue

### Scheduled Mode (`--cron`)

**Tier 1: Claude Code** — use `/loop` or `CronCreate`:

```
/loop <duration> /goalexec --validate
```

Or:
```
CronCreate with cron="*/<minutes> * * * *" (every N minutes)
prompt="/goalexec --validate"
recurring=true
```

**Tier 2: cmux reinjection** (any agent in a cmux pane) — use launchd + cmux:

```bash
scripts/goalexec-loop-cmux.sh --install --goal "<goal text>" --interval 5m
```

This is the same pattern as `scripts/monitoring/worldarchitect-ao-eloop.sh`:
1. Detects cmux socket and coder pane UUID
2. Saves target to `~/.goalexec-loop/cmux-target.env`
3. Installs a launchd LaunchAgent that fires every N seconds
4. Each fire reads the goal file and reinjects `/goalexec --validate` into the coder pane
5. Auto-uninstalls on CONVERGED or max iterations

```bash
# Commands
scripts/goalexec-loop-cmux.sh --install --goal "Fix lint errors" --interval 10m --max-iterations 15
scripts/goalexec-loop-cmux.sh --status           # check loop status
scripts/goalexec-loop-cmux.sh --uninstall         # stop and remove launchd agent
scripts/goalexec-loop-cmux.sh --cmux-detect      # detect cmux target and exit
```

**Tier 3: bash CLI loop** (no cmux, any terminal) — use `scripts/goalexec-loop.sh`:

```bash
scripts/goalexec-loop.sh --goal "<goal text>" --interval <seconds>
```

The bash script auto-detects which CLI to call (`opencode run` or `claude -p`) and runs a real while-loop:
1. Invokes `/goalexec --validate` each iteration
2. Checks `goals/.current-goal` for convergence status
3. Sleeps for the interval between iterations
4. Stops on CONVERGED, STALLED (same score 2x), or max iterations

```bash
# Commands
scripts/goalexec-loop.sh --goal "Fix lint errors" --interval 120 --max-iterations 15
scripts/goalexec-loop.sh --validate
scripts/goalexec-loop.sh --current
scripts/goalexec-loop.sh --clear
scripts/goalexec-loop.sh --dry-run --goal "test"
```

**Important:** `ScheduleCron` does NOT exist in any agent. The correct Claude Code tool is `CronCreate`.

## Validation Mode: --validate

1. Load `goals/.current-goal`
2. Check each criterion systematically:
   - File existence → Read tool
   - Tests pass → run test command, check exit code
   - PR state → `gh pr view`
   - Feature working → targeted functional check
3. Calculate completion percentage
4. Report status

### Validation Output Format

```
Goal Validation Report

Goal: <statement>
Status: CONVERGING (67% - 2/3 criteria)

Criteria:
1. ✅ <criterion> — <evidence>
2. 🔄 <criterion> — <partial evidence>
3. ❌ <criterion> — <failure reason>

Next: <specific steps to address remaining>
```

## Display Mode: --current

Read and display `goals/.current-goal` with all criteria.

## Clear Mode: --clear

Remove `goals/.current-goal` and any session state.

## Session State

Single flat file `goals/.current-goal` stores:
- Goal statement + success criteria
- Iteration count, last score, convergence status
- Validated criteria results

## Criteria Extraction Patterns

| Goal phrase | Criterion |
|-------------|-----------|
| "Create X" | X exists with correct content |
| "Fix Y" | Y no longer fails |
| "PR merged" | PR state = MERGED |
| "All tests pass" | Test exit code = 0 |
| "Implement Z" | Z works as specified |
