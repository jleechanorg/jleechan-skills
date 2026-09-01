# Archived Commands: Legacy Experiments

**Archival Date**: 2026-09-01 (`/ao`, `/auton` restored 2026-09-01 — AO tooling is still actively used)
**Reason**: Zero callers across all active skills/commands and 0 invocations in 30-day telemetry audit.

---

## Inventory of Archived Commands (11 Total)

### 1. Sunsetted Roadmap/Subagent Launcher Commands
- `/agentor`: alias entry — see `.claude/commands/extended-library/agento_report.md` frontmatter, unrelated to AO
- `/roadmap_orch`: Roadmap orchestrator
- `/roadmapo`: Roadmap orchestrator alias
- `/suba`: Legacy subagent launcher
- `/subagentvalidate`: Legacy subagent validator

### 2. Historical Copilot & Pair Experiments
- `/copilot-expanded`: Historical pre-subagent copilot prompt
- `/pairv2`: Historical dual executor launcher v2
- `/pair-examples`: Dual executor examples

### 3. Legacy WorldAI Campaign Tools
- `/idice`: Legacy WorldAI dice campaign inspector
- `/investigatedice`: Legacy WorldAI dice campaign inspector
- `/topcampaigns`: Legacy WorldAI campaign rankings

---

## Recovery Instructions

To restore any command to active status, use `git mv`:

```bash
git mv .claude/commands_archive/2026-09-01-sunsetted-legacy-commands/<command-name>.md .claude/commands/extended-library/<command-name>.md
```
