# Installation

This export is skills-first: every canonical package is under
`.claude/skills/<skill>/SKILL.md`; slash-command files are optional pointers.

The bundled installer copies four component trees into `CLAUDE_HOME`:

| Source | Destination (when `CLAUDE_HOME` is unset) |
| --- | --- |
| `.claude/agents/` | `~/.claude/agents/` |
| `.claude/commands/` | `~/.claude/commands/` |
| `.claude/scripts/` | `~/.claude/scripts/` |
| `.claude/skills/` | `~/.claude/skills/` |

Set `CLAUDE_HOME` to select a destination. The installer refuses a nonempty target by default; use
`--backup` to move that target to a timestamped sibling directory before
installing, or `--merge` only when you deliberately want source-managed files
updated in place. A routine merge reports but preserves active files whose
names collide with archived packages. Add `--migrate-archives` only after
reviewing those collisions and deciding they are the retired managed copies.

## Isolated install and verification

This runs the real installer without changing your normal agent configuration:

```bash
INSTALL_ROOT=$(mktemp -d /tmp/jleechan-skills.XXXXXX)
git clone https://github.com/jleechanorg/jleechan-skills.git "$INSTALL_ROOT/source"
CLAUDE_HOME="$INSTALL_ROOT/claude" \
  bash "$INSTALL_ROOT/source/install-claude-commands.sh"

test -f "$INSTALL_ROOT/claude/skills/repro-evidence/SKILL.md"
test -f "$INSTALL_ROOT/claude/commands/er.md"
```

The two `test` commands must exit zero. This verifies the installed skill and
command files directly; it does not assume `/help` or `/list` is available in
every host application. Inspect an installed skill with:

```bash
sed -n '1,80p' "$INSTALL_ROOT/claude/skills/repro-evidence/SKILL.md"
```

When finished, remove only the exact temporary directory printed by your shell:

```bash
rm -rf "$INSTALL_ROOT"
```

## Install into your normal Claude home

Only do this after an isolated run succeeds. `--backup` is the safe default for
an existing Claude home: it moves the complete old target aside before writing
the new one. Record the timestamped backup path printed by the installer.

```bash
CLAUDE_ROOT="${CLAUDE_HOME:-$HOME/.claude}"
SOURCE_ROOT=$(mktemp -d /tmp/jleechan-skills-source.XXXXXX)
git clone https://github.com/jleechanorg/jleechan-skills.git "$SOURCE_ROOT"
CLAUDE_HOME="$CLAUDE_ROOT" bash "$SOURCE_ROOT/install-claude-commands.sh" --backup
```

To install into an empty target, omit the flag. To intentionally update an
existing target without moving it aside, use `--merge`:

```bash
CLAUDE_HOME="$CLAUDE_ROOT" bash "$SOURCE_ROOT/install-claude-commands.sh" --merge
```

If that command reports archive collisions, review each path. To move those
specific same-named active packages into the sibling archive roots, rerun with:

```bash
CLAUDE_HOME="$CLAUDE_ROOT" \
  bash "$SOURCE_ROOT/install-claude-commands.sh" --merge --migrate-archives
```

Restart the host application after installing if it only discovers skills and
commands at startup. For project-local use, copy complete skill directories to
your project's `.claude/skills/`; never copy an individual `SKILL.md`, because
a package can include scripts and references.

## Rollback

Do not delete `~/.claude/commands` or other shared directories to “uninstall”
this export: they can contain unrelated user configuration. If you installed
with `--backup`, move the post-install target aside and put the recorded backup
path back in its place:

```bash
CLAUDE_ROOT="${CLAUDE_HOME:-$HOME/.claude}"
BACKUP_ROOT="/absolute/path/reported-by-the-installer"
RECOVERY_ROOT="${CLAUDE_ROOT}.after-jleechan-skills-$(date +%Y%m%d%H%M%S)"
mv "$CLAUDE_ROOT" "$RECOVERY_ROOT"
mv "$BACKUP_ROOT" "$CLAUDE_ROOT"
```

This preserves the post-install state in `RECOVERY_ROOT` for review. An
in-place `--merge` install has no exact automatic rollback, because it may have
replaced same-named files; restore a backup you made before merging.

For an isolated install, rollback is simply removal of its exact
`$INSTALL_ROOT` directory shown above.

## Use the installed skills

Read a skill before invoking it. Examples present in this export include
`repro-evidence`, `evidence-review`, `parallelize-to-ceiling`, and `redgreen`.
Their canonical instructions are respectively at:

- [`.claude/skills/repro-evidence/SKILL.md`](.claude/skills/repro-evidence/SKILL.md)
- [`.claude/skills/evidence-review/SKILL.md`](.claude/skills/evidence-review/SKILL.md)
- [`.claude/skills/parallelize-to-ceiling/SKILL.md`](.claude/skills/parallelize-to-ceiling/SKILL.md)
- [`.claude/skills/redgreen/SKILL.md`](.claude/skills/redgreen/SKILL.md)

See [README.md](README.md) for the catalog and [GitHub Issues](https://github.com/jleechanorg/jleechan-skills/issues) for support.
