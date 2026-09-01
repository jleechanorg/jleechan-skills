# Archived Skills: Sunsetted AO Suite & Generic Principles

**Archival Date**: 2026-09-01  
**Reason**: Superseded by modern subagent delegation, Dark Factory (`/f`), Codex parallel lanes (`/parallel`), and repo harness engineering (`4layer`). All cross-references cleanly refactored. Zero invocations in 30-day telemetry audit.

---

## Inventory of Archived Skills (11 Total)

### 1. Sunsetted AO / OpenClaw Daemon Suite
- `auton`: Legacy retrospective diagnostic for the OpenClaw / Agent Orchestrator (AO) lifecycle daemon. Superseded by `/harness-postmortem` and `/history-resume`.
- `agent-orchestrator`: Legacy AO launcher package. Superseded by `/parallel` and direct subagents.
- `ao-lifecycle-triage`: Triaged crashed AO daemon workers. Superseded by Dark Factory.
- `ao-model-override`: Historical AO YAML model switcher. Superseded by CLI runtime flags.
- `ao-operator-discipline`: Historical AO parameter rules. Superseded by modern Codex agent rules.
- `ao-session-monitor`: Monitored tmux unicode spinners for AO workers. Superseded by `cmux` and subagent transcripts.
- `ao-spawn-gate`: AO spawn rate limiter. Superseded by parallel resource admission gates.
- `ao-spawn-safety`: AO worker session caps. Superseded by subagent isolation.
- `ao-worker-dispatch`: Dispatched tasks to `jc-*` tmux workers. Superseded by `invoke_subagent` and Codex lanes.

### 2. Generic Textbook Principles
- `solid`: Generic textbook OOP tutorial prompt. Superseded by concrete repo contracts (`harness-engineering`, `4layer`, `root-cause-first`).

### 3. Historical Pair Benchmarks
- `pairv2-usage`: Early 2026 LangGraph-based pair benchmarking runner. Superseded by `/parallelize-to-ceiling`.

---

## Recovery Instructions

To restore any skill to active status, use `git mv`:

```bash
git mv .claude/skills_archive/2026-09-01-sunsetted-ao-and-generic/<skill-name> .claude/skills/<skill-name>
```
