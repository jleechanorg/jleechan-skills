# Historical zero-use archive — 2026-08-27

These skills were removed from the installable catalog, not deleted. This
directory is a sibling of `skills/`, so the installer never copies it and no
archived package participates in skill discovery. Restore a package with
`git mv` if a live workflow needs it again.

## Evidence

The 30-day Claude Code history pass (2026-07-28 through 2026-08-27) inspected
structured assistant `Skill` tool calls rather than raw text mentions. It found
zero calls for each archived package:

- `agent-orchestrator`
- `codex-evolve-loop`
- `skeptic-agent`

The following packages also have a canonical active counterpart and are visibly
historical copies by name. They have zero structured calls and no active
project caller:

- `dark-factory.bak.1784359965` → `dark-factory`
- `factory-spec.bak.1784359965` → `factory-spec`
- `fix-completion-deploy.pre-user-scope-20260727T035804Z` → `fix-completion-deploy`
- `design-doc-backup-worldarchitect` → `design-doc`

Raw-name records were intentionally ignored: they are dominated by skill
catalogues and documentation, and are not invocation evidence. The three
packages also have no project slash-command pointer. `skeptic-agent` is
explicitly marked as a deleted system in its own historical content.

## Scope

This archive contains 115 packages. The broader tranche applies the same
evidence rule to the active catalog: no structured Skill call in 30 days and
no reference from an observed-used skill, active slash command, or global
operating contract. Explicit repository contracts remain active even when they
have no recent call, including `superpowers-quick`, `command-research`, AO
workflow skills, and portability-test members.

`loop-level-zfc` joined this archive after its zero-use, no-caller command
`loop_level_zfc` moved to the sibling command archive.
