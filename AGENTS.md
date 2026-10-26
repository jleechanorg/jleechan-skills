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

## PR workflow discovery

Use [.claude/skills/pr-workflow-manager/SKILL.md](.claude/skills/pr-workflow-manager/SKILL.md) as the entry point and [.claude/skills/pr-lifecycle/SKILL.md](.claude/skills/pr-lifecycle/SKILL.md) as the shared default lifecycle contract. This repository explicitly opts into its visible six-stage title/label/body workflow. Keep these references and the entry point synchronized with the contract; do not duplicate the stage rules here or in a design document. Other repositories and user-level AGENTS guidance should use the entry point's verified-checkout/clone-if-absent discovery procedure and preserve local changes.
