# Claude Code Guide

Use this repository as a portable skills export.

- Read the relevant `.claude/skills/<name>/SKILL.md` before using a workflow.
- Prefer skills over command documentation; commands are shortcuts.
- **Portability & Zero-PII Invariant**: Enforce complete removal of user-specific data that is not machine-portable, including personal email addresses, personal names, account identifiers, credentials, and non-portable user/home paths (`/home/<user>/...`, `/Users/<user>/...`).
- Never hardcode personal accounts, emails, or personal workspace locations into exported skills, commands, scripts, or documentation.
- Use generic placeholders, environment variables (`$HOME`, `$USER`, etc.), or machine-local configuration files (e.g. `~/.config/<tool>/config.json`) for machine- or user-specific settings.
- Put reusable scripts in `scripts/` and tests in `tests/`.
