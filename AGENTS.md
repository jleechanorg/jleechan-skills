# Repository Guide

This repository exports portable agent skills. Keep the root limited to package
metadata, public documentation, and the installer.

- Canonical skills live in `.claude/skills/`; slash commands are thin pointers.
- Put reusable scripts in `scripts/`, not the repository root.
- **Portability & Zero-PII Invariant**: Enforce strict exclusion of non-portable, user-specific data including personal email addresses, personal names, account identifiers, and machine-specific personal home paths (`/home/<user>/...`, `/Users/<user>/...`).
- Exported skills and tools must rely on generic interfaces, environment variables, or machine-local configuration files (`~/.config/<tool>/config.json`) rather than hardcoded personal configuration.
- **Fresh-machine, any-developer invariant**: Every exported skill, command, script, and doc must work for a different developer on a brand-new machine working in any repository. Do not assume:
  - a specific machine, OS install, hostname, LAN/tailnet address, SSH alias, or companion host (for example "the Mac mini" or "the Ubuntu box");
  - a specific checkout location (`~/projects/<repo>`, `$HOME/projects_other/...`) or that any particular repository is cloned locally;
  - a specific target product or repository (for example WorldArchitect.AI, `mvp_site/`, a named GitHub org or repo other than this one), its file layout, test commands, deploy targets, cloud projects, datasets, or Slack channels;
  - pre-installed personal tooling, wrappers, aliases, or install paths (`/opt/homebrew`, `~/.local/bin/<tool>`, shell functions from a personal `~/.bashrc`) beyond what the skill documents as a prerequisite.
- Resolve such values at run time instead: from the current working repository (`git rev-parse --show-toplevel`), a documented environment variable with a safe default or a clear "not configured" failure, or a machine-local config file. When a required value or tool is absent, report the missing prerequisite and stop or degrade gracefully; never guess a path, host, or repository.
- Content that only makes sense for one product or repository belongs in that repository's own `.claude/skills/`, or in an opt-in plugin folder under `plugins/<name>/`, never in the generic `.claude/skills/` export. Generic skills may point to such companions only by a discoverable convention (for example "a repo-local `user-story-*` skill, if present"), not by a hardcoded name or path.
- Preserve unrelated worktree changes and never commit credentials or sensitive data.
- Verify installer and relevant tests after changing exported content.
- Track planned work with Beads.

## Testing policy

- Do not write tests that pin prose in Markdown or instruction files (`SKILL.md`, `.claude/commands/*.md`, `AGENTS.md`, `CLAUDE.md`, README, `docs/`, `md_files/`): no `assertIn`/`assertNotIn` of phrases or sentences, no phrase-order checks, no "old wording must not reappear" bans. Skill and instruction wording is reviewed by humans and independent LLM review, not frozen by tests.
- Tests are allowed only for:
  - (a) executable behavior: scripts, installers, CLIs, generated output that a program consumes, and runnable snippets that a test extracts from Markdown and executes.
  - (b) mechanical structural invariants: files exist or are executable; frontmatter parses and its name matches the directory; internal links and heading anchors resolve; JSON/YAML parse; the zero-PII and portability scans that enforce the `CLAUDE.md` invariant; counts that must match the filesystem; literal tokens a program parses out of Markdown (frontmatter keys, stage label names, PR-body markers such as `**Evidence**:`).
- Keep the suite minimal: add a test only when it catches a real, mechanical failure. Prefer deleting a brittle test over updating it to match new wording. A policy or skill edit does not need a new test.
- For PRs with more than 50 changed lines across the full diff (additions plus deletions, across all file classes), require both `/ponytail` and `/cs` before readiness unless the canonical PR lifecycle positively selects its Markdown instruction-only route. That route uses its size- and risk-based full-scope AI review and scenario receipt instead of automatic `/cs`/Ponytail review by file size alone. Exactly 50 changed lines does not trigger this rule.
- The `/cs` review may satisfy `/ponytail` when it includes an explicit Ponytail-lane verdict; do not run that lane twice. Review tests for executable behavior or mechanical structural invariants, never for Markdown wording.
- When editing a skill breaks an existing wording-pin test, delete that assertion; do not restore the old wording. Deleting pins still goes through the normal PR workflow and review; it never qualifies a change for the one-liner fast path.

## PR workflow discovery

Use [.claude/skills/pr-workflow-manager/SKILL.md](.claude/skills/pr-workflow-manager/SKILL.md) as the entry point and [.claude/skills/pr-lifecycle/SKILL.md](.claude/skills/pr-lifecycle/SKILL.md) as the shared default lifecycle contract. This repository explicitly opts into its visible six-stage title/label/body workflow. Keep these references and the entry point synchronized with the contract; do not duplicate the stage rules here or in a design document. Other repositories and user-level AGENTS guidance should use the entry point's verified-checkout/clone-if-absent discovery procedure and preserve local changes.
