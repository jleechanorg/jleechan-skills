# Archived Skills: Sunsetted AO Config & Safety Modules

**Archival Date**: 2026-09-01  
**Reason**: Superseded by modern subagent delegation, Dark Factory (`/f`), Codex parallel lanes (`/parallel`), and repo harness engineering (`4layer`). Zero callers across all active skills/commands and 0 invocations in 30-day telemetry audit.

---

## Inventory of Archived Packages

1. **`ao-model-override`**: Historical AO YAML model switcher. Superseded by CLI runtime flags.
2. **`ao-spawn-safety`**: Historical AO worker session caps. Superseded by subagent isolation.

---

## Recovery Instructions

To restore any skill to active status, use `git mv`:

```bash
git mv .claude/skills_archive/2026-09-01-sunsetted-ao-and-generic/<skill-name> .claude/skills/<skill-name>
```
