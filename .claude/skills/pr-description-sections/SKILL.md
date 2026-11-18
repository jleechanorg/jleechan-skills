---
name: pr-description-sections
description: "Use when writing PR descriptions; follow the shared PR-description owner and the target repository's template."
---

# PR description guidance

The shared required structure and ordering are owned by `~/.codex/AGENTS.md` § PR descriptions (canonical owner),
with full section details preserved below so agents loading this skill get the complete formatting specification:

1. **Open** with one sentence of production vs non-production line deltas before any heading
   (e.g. `Line deltas: prod +42/-10 across 3 files; non-prod +18/-3 across 5 files.`), refreshed whenever the diff changes.
2. **Plain-language body** (written for a reader with zero context; final state, not a checkpoint log; explain jargon plainly):
   one-sentence summary; background (what and why now); goals; user story with before/after (or
   `No user-facing change — <reason>.`); tenets (with governing bead or design-doc link); what changed by area with line
   counts; test plan with evidence; risks and known limits; out of scope and follow-ups.
3. **`## Line Deltas (Prod vs Non-Prod)`** (visible): per-file added/deleted lines and totals for production runtime files
   versus non-production tests, fixtures, docs, CI, and scripts against the full PR base diff (not net additions).
4. **Evidence and review-gate records** after that. Put superseded checkpoint history inside a collapsed `<details>` block.
5. **`## Advice Approval` is the last section.** When `/advice` or `/wa` approves, write `APPROVED at <SHA> by <reviewers>`
   as its first line (immutable SHA-bound per `~/.claude/skills/pr-lifecycle/SKILL.md` § SHA-binding rule; retain prior
   reviewer attribution, SHAs, and receipts). Before finishing any PR create/edit, run `/ds` on the visible human body.

Also read the target repository's `AGENTS.md`/`CLAUDE.md` and `.github/pull_request_template.md` for local
required fields, CI markers, evidence records, and domain-specific content. Preserve those requirements while
applying the shared structure. Do not replace a repository template or local gate with this skill.
