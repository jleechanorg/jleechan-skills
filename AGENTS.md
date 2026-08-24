# Repository Guide

This repository exports portable agent skills. Keep the root limited to package
metadata, public documentation, and the installer.

- Canonical skills live in `.claude/skills/`; slash commands are thin pointers.
- Put reusable scripts in `scripts/`, not the repository root.
- Preserve unrelated worktree changes and never commit credentials.
- Verify installer and relevant tests after changing exported content.
- Track planned work with Beads.
