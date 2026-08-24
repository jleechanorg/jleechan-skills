# `.claude/commands/extended-library/` — 211 namespaced commands

**Created 2026-08-24.** Not the same thing as `archive/commands/`. See [README.md](README.md) for the side-by-side comparison of the two mechanisms.

## The one thing to know

These commands are **live and invocable**. They were moved, not archived. The invocation name changed:

```bash
/thermo                    # ❌ no longer resolves
/extended-library:thermo   # ✅ same file, namespaced name
```

This is a real, user-visible behavior change. Anything that calls one of these 211 by its bare `/<name>` — muscle memory, scripts, or a cross-reference inside another command file — needs the `extended-library:` prefix. It is not seamless and should not be described as such.

## Why this works

Claude Code discovers command files under `.claude/commands/` recursively and exposes files in a subdirectory under a directory-qualified name, `<subdirectory>:<filename>`. This was verified empirically before any files were moved, not assumed:

- Official docs (`code.claude.com/docs/en/slash-commands`) document the directory-qualified naming rule for nested skills, and state that commands and skills share one namespace.
- This repo already had command files in subdirectories before the migration — `.claude/commands/spec-kit/*.md` and `.claude/commands/backup-2026-06-27-team-claude-no-teamcreate/*.md`. A live session's own command listing showed them as `spec-kit:clarify`, `spec-kit:spec`, `backup-2026-06-27-team-claude-no-teamcreate:team-claude`, and so on — namespaced, and visible.

(Other pre-existing subdirectories — `cerebras/`, `_copilot_modules/`, `tests/`, `_shared/` — hold supporting scripts and partials rather than command `.md` files, so they correctly do not appear in the command listing.)

## Selection criterion

**Hard cutoff, no dependency-closure softening.** Active Core = top-20-most-human-typed ∪ top-20-most-agent-driven, measured against the frozen snapshot `usage_snapshot_frozen_2026-08-23.json` (`2026-08-24T010617Z`). The two lists overlap by 13, so the union is 27. `/innov` is a forced 28th include. Everything else — 239 − 28 = **211** — moved here.

The 28 that stayed flat:

`advice`, `auto`, `browser`, `browserclaw`, `claw`, `copilot`, `end2end-testing`, `er`, `es`, `execute`, `f`, `fixpr`, `green`, `harness`, `history`, `innov`, `learn`, `levelup`, `linux`, `ms`, `nextsteps`, `repro`, `research`, `roadmap`, `skillify`, `smoke`, `web-advice`, `wiki-search`

The verbatim 211 list is frozen in [ARCHIVE-DECISION-2026-08-23.md](ARCHIVE-DECISION-2026-08-23.md). To read the current state off disk instead:

```bash
ls .claude/commands/extended-library/*.md | xargs -n1 basename | sed 's/\.md$//'
```

## The disclosed trade-off

A dependency-closure computation ([CLOSURE-REPORT-2026-08-23.md](CLOSURE-REPORT-2026-08-23.md)) showed that references from the kept commands actually reach 94 commands, and an earlier recommendation in the same session proposed keeping all 94. That was explicitly overridden in favor of the hard cutoff.

The cost is real and was accepted knowingly: some cross-references from an Active Core command now point at a command whose name has changed. `tests/test_command_archive_migration.py` pins those crossings — it asserts every promoted→extended reference resolves to a file that actually exists in `extended-library/`, and deliberately fails if the crossing set is ever empty (which would mean the test had gone vacuous).

## Promoting a command back to Active Core

```bash
git mv .claude/commands/extended-library/<name>.md .claude/commands/<name>.md
```

Note that `tests/test_command_archive_migration.py` asserts exact counts (28 flat, 211 nested) against the lists in the decision doc, so a promotion is not just a file move — update the decision doc's Promoted and extended-library lists in the same change, or the test will correctly go red.
