# Empirical Skill & Command Usage Quantification System Design Specification

## Overview

This specification defines the architecture for a verified, empirical usage measurement system across all agent execution runtimes (Claude Code, Hermes, Codex, and Antigravity). It formally resolves the distinction between **human-typed slash commands** (`/command`) and **agentic skill invocations** (`Skill` tool calls, autonomous subagent dispatches, and auto-resolver triggers), addressing open bead `bd-cmdtop40-skills-usage-measurement-mtq`.

---

## Problem Statement & Empirical History

### 1. The Substring-Count Trap (Historical Failure)
- **Incident (2026-07-12, `jleechan-q0w`):** Initial attempts to measure command and skill frequency used raw substring matching (`content.count("name")`).
- **Failure Mode:** Generated 10,000 to 184,000 false-positive hits per skill/command name across `~/.claude/projects/*/*.jsonl` (e.g., `converge`, `reviewdeep` had zero actual invocations but showed tens of thousands of hits).
- **Root Cause:** Claude Code injects the entire catalog of available skills and commands as a system-reminder boilerplate in nearly every conversation turn.

### 2. What Is Currently Proven vs. What Is Unproven
- **PROVEN & WORKING (Slash Commands):** 
  - Exact tag matching (`<command-name>/X</command-name>`) for Claude Code JSONL logs.
  - Regex prompt-start token matching (`(?:^|\s)/cmd`) combined with human role filtering (`role == 'user'`, interactive TTY / non-bot user IDs) in `.claude/skills/command-research/scripts/count_command_usage_unified.py`.
  - Accurately ranks top user-typed commands (e.g., `/copilot` [552], `/claw` [363], `/e` [236], `/er` [203], `/status` [161], `/fixpr` [82], `/research` [75], `/4layer` [69], `/harness` [30]).
- **NOT YET PROVEN (Skill Usage):**
  - Slash command frequency does **not** equal skill usage. Skills are primarily invoked via:
    1. Direct human slash pointer invocation (e.g., `/advice`).
    2. Model tool calls (`tool_name == "Skill"` or `invoke_skill` with `{"skill_name": "..."}`).
    3. Implicit auto-resolver skill injection (context matches triggering keywords).
  - As documented in `bd-cmdtop40-skills-usage-measurement-mtq`, no existing pipeline currently aggregates `tool_calls` payloads across Claude Code, Hermes SQLite, and Codex SQLite to rank actual skill consumption.

---

## Assumptions and Recommended Defaults

To ensure deterministic execution and prevent unverified assumptions, the following defaults are selected:

1. **Dual-Channel Metric Model (Recommended):**
   - **Metric A: Human-Typed Invocations (`typed_count`)** — Explicit `/command` or `/skill` typed directly by the human in interactive sessions.
   - **Metric B: Model Tool Invocations (`tool_call_count`)** — Explicit `tool_calls` where an LLM invokes `Skill` / `invoke_skill` or loads a `SKILL.md` dynamically.
   - **Metric C: Subagent Dispatches (`subagent_dispatch_count`)** — Background lane / sidekick executions specifying the skill name.
   - Total Weighted Signal = `typed_count * 3 + tool_call_count * 2 + subagent_dispatch_count * 1`.

2. **Source Repositories & Data Stores:**
   - **Claude Code:** `~/.claude/projects/*/*.jsonl` (Parse `type: "user"` message content tags + `type: "assistant"` message `tool_calls`).
   - **Hermes:** `~/.hermes/state.db` (Parse `sessions.source` for interactive users; parse `messages.tool_name` / `messages.tool_calls` for tool executions).
   - **Codex:** `~/.codex/state_5.sqlite` (Parse thread messages and agent tool execution items).
   - **Antigravity:** `~/.gemini/antigravity-cli/brain/*/transcript.jsonl` (Parse `PLANNER_RESPONSE` tool calls).

3. **Performance & Indexing Safety:**
   - Always query SQLite with time bounding via `sessions.started_at >= ?` indexed scans, never unindexed full-table message scans.
   - For Claude Code JSONL files, filter by file modification time (`os.path.getmtime(fpath) >= cutoff`) before reading line-by-line.

4. **Scope Isolation:**
   - Enforce repository-scoped vs global-scoped filtering to prevent phantom global commands from corrupting repository rankings (resolving `bd-cmdtop40-scanner-global-scope-bug-3qk`).

---

## Architectural Approach & Data Pipeline

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                          Unified Skill Usage Pipeline                          │
├─────────────────────┬────────────────────┬───────────────────┬────────────────┤
│ Claude Code JSONL   │ Hermes SQLite      │ Codex SQLite      │ Antigravity    │
│ (~/.claude/projects)│ (~/.hermes/state)  │ (~/.codex/state_5)│ (brain logs)   │
└──────────┬──────────┴─────────┬──────────┴─────────┬─────────┴────────┬───────┘
           │                    │                    │                  │
           ▼                    ▼                    ▼                  ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                            Extractor & Normalizer                              │
│ • Channel 1: Human Typed (<command-name>/X, promptSource=typed, human role)    │
│ • Channel 2: Agent Tool Call (tool_name in ['Skill', 'invoke_skill'])          │
│ • Channel 3: Autonomous Dispatch (Sidekick/Swarm/AO task definitions)          │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                             Aggregator & Filter                                │
│ • Anti-Noise: Exclude system reminders, markdown tables, code paths            │
│ • Alias Resolution: Canonicalize (/ms -> memory-search, /f -> dark-factory)    │
│ • Scope Filtering: Filter strictly to repo-resident skills vs global system    │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                               Reports & Outputs                                │
│ • JSON Dataset: docs/evidence/skill-usage-report.json                          │
│ • Markdown Matrix: Ranked top-40 skills by human vs tool vs agent usage        │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Validation & Regression Contracts

1. **Synthetic Noise Test:** Scanner must score 0 hits on simulated system-reminder blocks containing all skill names.
2. **Tag Accuracy Test:** Scanner must record exactly 1 hit for `<command-name>/advice</command-name>`.
3. **Tool Call Accuracy Test:** Scanner must record exactly 1 tool hit for `{"name": "Skill", "input": {"skill": "4layer"}}`.
4. **Hermes & Claude Scope Separation:** Global commands without matching repo files must be flagged or filtered per configuration.

---

## Implementation Preconditions

- Script lives in `.claude/skills/command-research/scripts/measure_skill_usage_unified.py`.
- Unit tests live in `tests/test_skill_usage_measurement.py`.
