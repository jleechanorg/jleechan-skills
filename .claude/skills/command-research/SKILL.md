---
name: command-research
description: Empirical Command & Skill Usage Research Protocol — Measure true human vs agentic slash command invocations across Hermes, Claude Code, and Codex session stores without substring noise
---

# Command Research Protocol (`/command-research`)

## Purpose
Measure and rank actual slash command and skill invocations across all primary agent runtime databases:
1. **Hermes SQLite** (`~/.hermes/state.db`)
2. **Claude Code JSONL** (`~/.claude/projects/*/*.jsonl`)
3. **Codex SQLite** (`~/.codex/state_5.sqlite`)

Provides strict filtering to eliminate the **system-reminder substring noise trap** and categorizes invocations into **Human-Typed** vs. **Agentic/Subagent**.

---

## 🚨 Anti-Noise Rules (Mandatory)

1. **Never Use Raw Substring Search**:
   - `content.count("cmd")` produces 10,000–180,000 false positives because Claude Code repeats the entire skill/command catalog in system reminders after tool calls.
   - Always match exact prompt-start tokens `(?:^|\s)/cmd` or canonical Claude tags `<command-name>/cmd</command-name>`.

2. **Always Exclude Filesystem Paths & URLs**:
   - Filter against `PATH_PREFIXES` (`/Users`, `/tmp`, `/dev`, `/api`, `/src`, `/tests`, `/var`, `/home`, etc.) and `FILE_SUFFIXES` (`.py`, `.md`, `.ts`, `.sh`, `.json`).

3. **Separate Human from Subagents**:
   - **Human-Typed**: Role `user`, source `slack`/`cli`/`telegram`, non-bot user IDs, promptSource `typed`/interactive, no subagent parent UUIDs.
   - **Agentic**: Subagent sessions (`isSidechain: true`), Stop-hook loops, automated test runners, cron tasks.

---

## 🛠️ Unified Scanner Script

The bundled multi-store scanner is located at:
`scripts/count_command_usage_unified.py`

### Common Invocations:

```bash
# Run full historical audit across all stores
python3 .claude/skills/command-research/scripts/count_command_usage_unified.py

# Scan only the last 30 days
python3 .claude/skills/command-research/scripts/count_command_usage_unified.py --days 30

# Output top 15 human-typed commands
python3 .claude/skills/command-research/scripts/count_command_usage_unified.py --top 15 --human-only

# Output as structured JSON for reporting
python3 .claude/skills/command-research/scripts/count_command_usage_unified.py --json
```

---

## Reference Lineage
- Provenance: `jleechan-q0w` / `jleechan-thin-skill-migration-emu` (2026-07-12)
- Lessons: `~/llm_wiki/raw/feedback_2026-07-12_usage-signal-substring-count-invalid.md`
- Wire Verification: `~/projects_other/claude_llm_proxy` system prompt captures
