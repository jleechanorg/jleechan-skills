# Archived Skills: Unused Skills

**Archival Date**: 2026-09-01 (AO suite restored 2026-09-01 — still actively used; `babysit` added same day)
**Reason**: Confirmed unused by the operator. AO daemon skills were briefly archived then restored once confirmed still in active use — see Recovery Instructions.

---

## Inventory of Archived Skills (3 Total)

### 1. Generic Textbook Principles
- `solid`: Generic textbook OOP tutorial prompt. Superseded by concrete repo contracts (`harness-engineering`, `4layer`, `root-cause-first`).

### 2. Historical Pair Benchmarks
- `pairv2-usage`: Early 2026 LangGraph-based pair benchmarking runner. Superseded by `/parallelize-to-ceiling`.

### 3. AO Worker Monitoring
- `babysit`: Watched AO worker tmux sessions (WORKING/IDLE/QUEUED/DEAD/COMPLETED) and auto-remediated stuck workers. Confirmed unused by the operator — not to be confused with `pr-babysit`, a separate, still-active PR/CI monitoring skill.

---

## Recovery Instructions

To restore any skill to active status, use `git mv`:

```bash
git mv .claude/skills_archive/2026-09-01-sunsetted-ao-and-generic/<skill-name> .claude/skills/<skill-name>
```
