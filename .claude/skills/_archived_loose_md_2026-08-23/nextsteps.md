---
name: nextsteps
description: "Default: update beads and ~/roadmap. Use --full for full situational assessment with memory sync, learnings, nextsteps doc, and GitHub issues."
---

# /nextsteps — Beads & Roadmap Update

## Default mode (no flags)

**Gather context, then make updates** — beads and `~/roadmap` only.

### 1. Gather context (parallel)

- `git log --oneline -10` — recent commits
- `br list --status open --limit 0` — open beads
- `ls ~/roadmap/` and read `~/roadmap/README.md` recent section
- Use any user-provided line after `/nextsteps` as extra context.

### 2. Update beads

- Match recent commits to open beads; close or update status.
- Note gaps → create new beads with `br create`.
  ```bash
  br create "<title>" --type task --priority 2
  br update <id> --status <new_status>
  ```

### 3. Update `~/roadmap`

- Append session bullet to **`~/roadmap/README.md`** under `## Recent activity` (create section if absent).
- Create `mkdir -p "$HOME/roadmap"` first if the directory may not exist.
- Keep appends concise — one or two bullets per session.

### 4. Report

- Beads updated/created (IDs and titles)
- `~/roadmap/README.md` changes made
- Recommended next actions

---

## `--full` mode

When invoked as `/nextsteps --full`, run the complete pipeline:

→ Follow `~/.claude/skills/nextsteps/SKILL.md` exactly (nextsteps doc, learnings, Claude auto-memory, mem0, GitHub issues).