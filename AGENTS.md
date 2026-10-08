# Repository Guide

This repository exports portable agent skills. Keep the root limited to package
metadata, public documentation, and the installer.

- Canonical skills live in `.claude/skills/`; slash commands are thin pointers.
- Put reusable scripts in `scripts/`, not the repository root.
- **Portability & Zero-PII Invariant**: Enforce strict exclusion of non-portable, user-specific data including personal email addresses, personal names, account identifiers, and machine-specific personal home paths (`/home/<user>/...`, `/Users/<user>/...`).
- Exported skills and tools must rely on generic interfaces, environment variables, or machine-local configuration files (`~/.config/<tool>/config.json`) rather than hardcoded personal configuration.
- Preserve unrelated worktree changes and never commit credentials or sensitive data.
- Verify installer and relevant tests after changing exported content.
- Track planned work with Beads.
