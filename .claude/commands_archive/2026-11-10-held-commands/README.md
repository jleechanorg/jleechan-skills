# Archived Commands: Held Back on 2026-11-10, Then Archived

**Archival Date**: 2026-11-10
**Reason**: These 33 command files were held back from `../2026-11-10-no-usage-evidence/` only because an active file still referenced them (the held table is in `docs/skill-archive-2026-11-09.md`). The operator does not use them and chose to archive them. Every active reference was removed or rewritten as a short inline instruction in the same change, so no active command, skill or agent invokes them.

---

## Inventory (41 files)

All came from `.claude/commands/extended-library/` unless noted.

### 1. The held command files (33)
`/archreview`, `/cerebras`, `/checkpoint`, `/coverage`, `/debug`, `/exportcommands`, `/gene`, `/gstatus`, `/guidelines`, `/header`, `/localexportcommands`, `/pair`, `/perp`, `/presentation`, `/principalengineer`, `/principalproductmanager`, `/push`, `/replicate`, `/requirements-list`, `/requirements-start`, `/requirements-status`, `/scaffold`, `/team-claude`, `/team-mini`, `/test`, `/teste`, `/tester`, `/testerc`, `/testhttp`, `/testhttpf`, `/testllm`, `/testuif`, `/think`

### 2. Pure aliases of an archived command (6)
- `/c`, `/cereb`, `/qwen`: aliases for `/cerebras`
- `/gen`: alias for `/gene`
- `/pres`, `/slide`: aliases for `/presentation`

### 3. Backup copies of archived commands (2)
- `backup-2026-06-27-team-claude-no-teamcreate/team-claude.md` and `team-mini.md`, from `.claude/commands/backup-2026-06-27-team-claude-no-teamcreate/`

`/arch` (alias for `/archreview`) and `/thinku` (alias for `/think ultra`) stay active: each is referenced by many active files, so its one-line body was rewritten as a self-contained instruction instead.

Companion scripts stay in place, as in the earlier group: `.claude/commands/cerebras/` (including `cerebras_direct.sh`, which the cerebras agents now call directly), `exportcommands.sh`, `gstatus.py`, `push.py`, `think.py`, `.claude/scripts/teste.sh`, `tester.sh`, `testerc.sh`, `pair_execute.py`.

---

## Recovery Instructions

```bash
git mv .claude/commands_archive/2026-11-10-held-commands/<command-name>.md .claude/commands/extended-library/<command-name>.md
```

The backup folder goes back with `git mv .claude/commands_archive/2026-11-10-held-commands/backup-2026-06-27-team-claude-no-teamcreate .claude/commands/backup-2026-06-27-team-claude-no-teamcreate`.

An alias needs its target restored with it: `c`, `cereb` and `qwen` need `cerebras`; `gen` needs `gene`; `pres` and `slide` need `presentation`. Restoring a command does not restore the references that were rewritten; re-add them by hand if needed.
