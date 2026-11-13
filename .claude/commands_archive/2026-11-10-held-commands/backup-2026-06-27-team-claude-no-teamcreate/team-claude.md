---
description: Create a Claude-native agent team with opus orchestrating sonnet/haiku workers
type: agent-orchestration
execution_mode: immediate
---

## EXECUTION INSTRUCTIONS FOR CLAUDE

**When this command is invoked, YOU (Claude) must execute these steps immediately:**

1. Parse the user's prompt from the command arguments
2. Create tasks using `TaskCreate` for each subtask (one task per lane/worker)
3. Spawn teammates using `Agent` with `name` parameter (set the `team_name` parameter too but expect it to be ignored — see Notes)
4. Coordinate via `SendMessage` and `TaskUpdate`
5. Shutdown teammates when complete

## HOW TEAM-CLAUDE WORKS

This command dispatches a **parallel subagent team** using the `Agent` tool with `run_in_background=true`. The current Claude Code session has a single implicit team; explicit `TeamCreate` calls are NOT supported in this environment (the tool is unavailable).

- **Opus** (you, the orchestrator/team lead) — plans, creates tasks, coordinates, reviews
- **Sonnet** teammates — `claude-pair-coder` and `claude-pair-verifier` for implementation and verification
- **Haiku** — quick tasks like file searches, simple checks, formatting

The team gets a shared task list, automatic message delivery between teammates, and coordinated task ownership.

## TEAM-CLAUDE COMMAND

Usage: `/team-claude <prompt>`

### Execution Steps:

1. **Create tasks** from the user's prompt:
   ```python
   TaskCreate(subject="<task>", description="<details>")
   ```
   Set up `blockedBy` dependencies between tasks where needed.

2. **Spawn sonnet teammates:**
   ```python
   Agent(
       subagent_type="claude-pair-coder",
       model="sonnet",
       name="coder-1",
       team_name="claude-team-<name>",
       description="<task description>",
       prompt="<detailed prompt>",
       run_in_background=True
   )
   ```
   ```python
   Agent(
       subagent_type="claude-pair-verifier",
       model="sonnet",
       name="verifier-1",
       team_name="claude-team-<name>",
       description="<verification description>",
       prompt="<detailed prompt>",
       run_in_background=True
   )
   ```

4. **Use haiku for lightweight tasks:**
   ```python
   Agent(
       model="haiku",
       name="scout",
       team_name="claude-team-<name>",
       description="<quick task>",
       prompt="<simple task prompt>"
   )
   ```

5. **Orchestrate via task list:**
   - Teammates check `TaskList` for available work
   - Claim tasks with `TaskUpdate(owner="coder-1")`
   - Mark tasks done with `TaskUpdate(status="completed")`
   - Communicate via `SendMessage(to="coder-1", message="...")`

6. **Shutdown teammates** when all tasks complete:
   ```python
   SendMessage(
       to="coder-1",
       message={"type": "shutdown_request", "reason": "All tasks complete"}
   )
   ```

### Notes (added 2026-06-27)

- The `TeamCreate` primitive described in earlier versions of this skill is **not callable** in the current Claude Code session. The `Agent` tool description explicitly notes `team_name (Deprecated; ignored. The session has a single implicit team.)`. Skip step 1 (team creation) and dispatch agents directly.
- If `TaskCreate` is unavailable in your session, fall back to `Agent` dispatch only and track work via the inbox messages instead.
- For minimax/M2.5 backend, use the sister command `/team-mini` (which uses `minimax-pair-coder` agent types that shell out to `claudem()` from `~/.bashrc`).

### Model Budget Rules:
- **Opus**: Only for orchestration decisions, final review, complex reasoning
- **Sonnet**: Primary workhorse — coding, testing, verification, code review
- **Haiku**: File lookups, simple checks, formatting, trivial subtasks
- **Goal**: Maximize sonnet usage, minimize opus token spend

### Key Differences from Raw Agent() Calls:
- **Shared task list** — all teammates see progress and can claim work
- **Message routing** — teammates can communicate with each other and the lead
- **Task ownership** — prevents duplicate work, tracks who's doing what
- **Idle management** — teammates wake up when messaged with new work
- **Graceful shutdown** — proper cleanup when work is done

### Batching & Parallelization Rules (MANDATORY — include in every teammate prompt)

Teammates must **never** make a sequence of independent tool calls one-at-a-time when they can be batched or parallelized. Wall-clock cost is dominated by round-trip latency, not by the work.

When briefing a teammate, **explicitly tell them to**:

1. **Chain independent CLI calls in a SINGLE Bash invocation** with `&&`, `;`, or a `for` loop:
   ```bash
   br create --title "A" ... && \
   br create --title "B" ... && \
   br create --title "C" ...
   ```
   Twelve `br create`s chained = ~3-5 s. Twelve separate tool round-trips = 10-15 minutes.

2. **Fan out to parallel sub-Agents** when work is naturally chunked and concurrent CLI use is safe. Dispatch them in **one message with multiple `Agent` calls**, each with `run_in_background=True`. Example: 12 beads → 3 sub-Agents × 4 beads each.

3. **Batch file edits**: use `MultiEdit` for multiple changes to the same file, or send multiple `Edit` calls in one message for different files.

4. **Default to batching.** A sequence of >3 independent tool calls is a red flag — stop and ask "can this be a single Bash call or a parallel sub-Agent fan-out?"

5. **Anti-pattern:** "I'll do A, then B, then C, then D..." in separate messages. Replace with "I'll do A+B+C+D in parallel".

If a teammate prompt has a "do NOT spawn child agents" constraint by default, **explicitly lift it** for batchable operations when steering: "I'm lifting the no-child-agent constraint for this batch operation."

### Example:
```
/team-claude Implement bd-awq PR poller plugin with TDD — write failing tests first, then implement
```
