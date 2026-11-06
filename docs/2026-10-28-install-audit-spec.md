# Specification — installer and documentation audit (2026-10-28)

Seven-element specification for the audit-fix bundle landed in this PR. It is
committed (rather than held in the PR body) because the complete diff is over
50 total additions+deletions.

## Outcome

`install-claude-commands.sh` stops crashing or corrupting installs on macOS
`/bin/bash` 3.2, stops archiving skills the source still ships active, rejects
`--merge --backup`, installs described aliases like `/rg`, and stops pulling
browser skills into the default and `prw` profiles. `exportcommands.sh` runs
under bash 3.2. README, INSTALL and the skill/command docs state the measured
profile counts and no longer cite retired flat `skills/<name>.md` paths or
non-existent `install/` templates.

## Non-goals

- No new installer features, flags, or profiles beyond the documented fixes.
- No change to approval, merge, review, evidence or security policy content;
  the skill edits in this PR are link/path corrections plus the `--with`
  documentation note.
- No mass migration of the archive; only the "never archive what the source
  ships active" rule from patch 0002.
- Not changing the published `--all` package set.

## Acceptance

1. On macOS `/bin/bash` 3.2:
   - `CLAUDE_HOME=$(mktemp -d)/h /bin/bash ./install-claude-commands.sh` exits 0,
     prints `Installation complete!`, and installs 20 skills for the default profile.
   - `bash .claude/commands/exportcommands.sh` (dry syntax + array guard path)
     does not die with `unbound variable`.
2. `--merge --migrate-archives` on a target with no archive collisions installs
   the profile and never moves a still-shipped skill into `skills_archive`.
3. `--merge --backup` is rejected in either flag order with a non-zero exit.
4. Default install includes `/rg`; default and `prw` installs contain no
   `aside-browser-default` or `browser-testing`; `--profile web` installs both.
5. Measured counts after the bundle: default 20/11/1, `highlights-prw` 30/18/1,
   `prw` 24/11/1, `web` 19/5/1, `--all` 274/243/45 — matching README and INSTALL.
6. No active skill, command or agent file cites `.claude/skills/<name>.md`
   when only `.claude/skills/<name>/SKILL.md` exists.
7. Full contract suite: no new failure versus the PR base commit.

## User stories

- As a maintainer installing on a stock macOS laptop, I get a working install
  instead of a silent exit-0 no-op or an `unbound variable` crash.
- As a maintainer re-running `--merge`, my active skills are not moved into the
  archive by the run that just installed them.
- As a reader of README/INSTALL, the skill counts and `--with` behaviour I see
  match what the installer actually does.
- As an agent reading a skill, the linked sibling skill path resolves.

No user-facing product UI changes; the CLI output and docs are the surface.

## Proof plan

- Base-vs-head contract suite with identical test identities and error text for
  every remaining failure (local baseline equality).
- `/bin/bash` 3.2 install smoke at head: exit code, `Installation complete!`,
  installed skill/command/agent counts.
- `exportcommands.sh` RED at base / GREEN at head under `/bin/bash` 3.2.
- Repo CI (`tests.yml`, ubuntu-latest, Python 3.11, Node 22) green at head.
- `git diff --numstat` full-diff line accounting for the PR body opener.
- Independent `/advice` reviewer votes and an independent evidence review.
- Visual proof: `N/A` — no rendered UI, screenshot, GIF or video is published
  or claimed by this PR; the changed surface is CLI text and Markdown source.

## Mock

No mock or fixture substitutes for a claimed behaviour. The installer/profile
tests drive the real scripts in temporary `CLAUDE_HOME` roots.

## Risk

- Installer behaviour changes (archive migration, alias closure, profile
  membership) are the highest-risk part; covered by the new and existing
  installer contract tests plus the clean-room bash 3.2 run recorded in the
  bundle README.
- Two intermediate commits are intentionally not green alone (0006 needs 0007,
  0009 needs 0012); the series lands as one PR.
- Doc counts can drift when skills are added upstream; the bundle records the
  measurement method so counts are re-measurable.
