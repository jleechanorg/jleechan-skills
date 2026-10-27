# Installation

For the curated native-tool derivatives, use the opt-in
[portable installation](portable/README.md). It requires a dedicated destination,
installs only its manifest scope, and leaves the canonical Claude workflows alone.

This export is skills-first: every canonical package is under
`.claude/skills/<skill>/SKILL.md`; slash-command files are optional pointers.

The default is now a curated profile, not the full library. With no flag the
installer copies the `highlights` profile: the six highlighted skills
(`superpowers-quick`, `advice`, `redgreen`, `4layer`, `evidence-review`,
`harness-engineering`), plus the in-repo skills they link to
(`../X/SKILL.md`, `~/.claude/skills/X/`, `$CLAUDE_HOME/skills/X/`), the
command aliases for the named skills together with any non-Markdown helper
under `commands/` they run, and the agents and scripts those files reference. A
skill that arrives only as a linked dependency brings no slash commands, and
a command counts as an alias only when its name is the skill, its frontmatter
description says "alias", or it is at most 15 lines; longer workflow commands
such as `/polish` and `/savetmp` need `--all`. Run
with `--all` for the old full install. Each profile installs its named set plus
linked dependencies; counts below are measured from a scratch install.

| Option | Named set (plus linked dependencies) | Skills / commands / agents |
| --- | --- | --- |
| *(none)* or `--profile highlights` | the six highlighted skills | 20 / 10 / 1 |
| `--profile highlights-prw` | `highlights` plus `prw` | 29 / 17 / 1 |
| `--profile prw` | 12 PR workflow skills plus `/es`, `/er`, `/green`, `/cs` | 23 / 11 / 1 |
| `--profile web` | `advice`, `web-advice`, `browser-control` | 17 / 5 / 1 |
| `--with SKILL` | add a named skill to the profile; repeatable | varies |
| `--all` | every package, as before | 267 / 243 / 45 |

Profiles live in `shared/install-profiles.json`; `--help` lists them. Closure
never adds a skill on that file's `closure_excluded` list (`dot`,
`dot-coordinator`, `agy-dot-coordinator`, `web-advice`, `browser-control`,
`slack-media-upload`, `github-cli-reference`, `claw-dispatch`,
`ao-operator-discipline`): they read browser cookies or depend on personal
infrastructure, so they install only under `--all`, a profile that names them,
or `--with`. Skills that link to one of them report it as unavailable. The
installer prints the profile and the number of skills, commands and agents it
installed. A profile install is additive: `--merge` never removes skills an
earlier `--all` install left behind, and `--backup`, `--merge`,
`--include-protected` and `--migrate-archives` behave the same with every
profile. `--portable` installs its own manifest and refuses profile flags. A
profile command whose target skill is on `closure_excluded` is refused unless
the profile names that skill or `--with` adds it, and malformed profile data
(any list field that is not a list of names) stops the install before writing.

For `--all`, the installer copies four component trees into `CLAUDE_HOME`:

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

Before writing, `--merge` copies every existing path whose content it would
change into `${CLAUDE_HOME}.merge-backup-<timestamp>-<pid>` and prints that
location; if the backup cannot be written it stops without overwriting
anything. It also leaves existing skills and commands (including those under
`commands/extended-library/`) alone when their name is listed in
`$CLAUDE_HOME/.jleechan-skills-protected` (one name per line, `#` comments) or
in this repository's `shared/retain-local.json` (when that file exists it must be
a non-empty JSON object of names: a directory, a dangling symlink, an unreadable
file, a JSON string or list, or an empty object stops the merge before any
overwrite), printing each skipped path;
`--migrate-archives` does not move them either. Every trailing slash is stripped
from `CLAUDE_HOME` first, so the backup directory always sits beside the target. Add `--include-protected` to
overwrite or migrate those as well (overwritten paths are still backed up
first).

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
in-place `--merge` install has no exact automatic rollback: copy the files you
need back from the `.merge-backup-*` directory it reported. Files the merge
added (absent before) are not in that backup.

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
