# Archived Commands: No Usage Evidence

**Archival Date**: 2026-11-10
**Reason**: The skill-form copies of these commands were archived on the operator's hosts for lack of usage evidence (no typed use, no file opens in Claude Code or Codex history), and no active skill or command still invokes them. The operator chose to archive the command files too.

Full classification, and the command files that were held back because an active file still references them, is in `docs/skill-archive-2026-11-09.md`.

---

## Inventory of Archived Commands (23 Total)

All came from `.claude/commands/extended-library/` unless noted.

### 1. Commands whose host-local skill copy was archived (16)
`/clonefix`, `/contexte`, `/ghfixtests`, `/handoff`, `/headless`, `/list`, `/optimize`, `/puppeteer`, `/reviewsuper`, `/runlocal`, `/simulate`, `/statusline`, `/testmcp`, `/timeout`, `/validate-e2e`, `/wiki-evolve`

### 2. Commands that only dispatched to a skill archived in the same change (5)
- `/coderabbit`: `coderabbit.md` (extended-library body) and `top-level/coderabbit.md` (the thin dispatcher from `.claude/commands/coderabbit.md`); skill `coderabbit`
- `/cr`: alias for `/coderabbit`
- `/goalexec_define`: skill `goalexec-define`
- `/pr-report`: skill `pr-report`

### 3. Pure aliases of an archived command (2)
- `/con`: alias for `/contexte`
- `/sim`: alias for `/simulate`

---

## Recovery Instructions

To restore any command to active status, use `git mv`:

```bash
git mv .claude/commands_archive/2026-11-10-no-usage-evidence/<command-name>.md .claude/commands/extended-library/<command-name>.md
```

The top-level dispatcher goes back with `git mv .claude/commands_archive/2026-11-10-no-usage-evidence/top-level/coderabbit.md .claude/commands/coderabbit.md`. A dispatcher needs its skill restored as well (see `.claude/skills_archive/2026-11-09-no-usage-evidence/README.md`).
