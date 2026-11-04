# Claude Code Guide

Use this repository as a portable skills export.

- Read the relevant `.claude/skills/<name>/SKILL.md` before using a workflow.
- Prefer skills over command documentation; commands are shortcuts.
- **Portability & Zero-PII Invariant**: Enforce complete removal of user-specific data that is not machine-portable, including personal email addresses, personal names, account identifiers, credentials, and non-portable user/home paths (`/home/<user>/...`, `/Users/<user>/...`).
- Never hardcode personal accounts, emails, or personal workspace locations into exported skills, commands, scripts, or documentation.
- Everything exported must work for another developer on a brand-new machine in any repository: no assumed hosts, checkout paths, target product/repo (e.g. WorldArchitect.AI), or personal tooling. See the fresh-machine invariant in `AGENTS.md`.
- Use generic placeholders, environment variables (`$HOME`, `$USER`, etc.), or machine-local configuration files (e.g. `~/.config/<tool>/config.json`) for machine- or user-specific settings.
- Put reusable scripts in `scripts/` and tests in `tests/`. Follow the testing policy in `AGENTS.md` (no wording-pin tests; keep tests minimal).
