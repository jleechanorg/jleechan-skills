# Archived Loose Skill Markdown Files (2026-08-23)

These were top-level loose `.md` skill files sitting directly under `.claude/skills/`.
Each file in this directory duplicated an already-existing `.claude/skills/<name>/SKILL.md`.
In every sampled case, the loose copy held staler content than the corresponding directory version.
The directory `.claude/skills/<name>/SKILL.md` versions are authoritative and were left untouched.

Files were archived using `git mv` rather than deleted so that every file stays fully recoverable via:
`git log --all --follow -- .claude/skills/<name>.md`

This is the second recurrence of the `bd-2w17` (2026-04-05) pattern.
See `.claude/skills/_archived_loose_md/README.md` for the prior instance.

To restore a file, move it back to the parent directory: `git mv <name>.md ../<name>.md`.
