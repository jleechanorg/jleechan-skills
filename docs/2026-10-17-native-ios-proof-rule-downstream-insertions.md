# Native iOS proof rule — downstream insertion points

Status: **canonical text landed here; downstream edits deliberately NOT applied.** This note is the
handoff for the paused downstream step.

Canonical owner: `md_files/AGENTS.shared.md` § *Native iOS proof for user-visible UI changes
(canonical)* (installs to `~/.codex/AGENTS.md` and is imported by `~/.claude/CLAUDE.md`).

Per § *Downstream repository pointers and production classification*, downstream repositories point at
the canonical file and never restate its text. So both downstream insertions below are **one pointer
bullet each** — no numbers, no gates, no duplicated evidence classes.

## 1. `jleechanorg/worldarchitect.ai` — `AGENTS.md`

- **File to edit:** `AGENTS.md` (in that repo `CLAUDE.md` is a symlink → `AGENTS.md`; edit `AGENTS.md` only).
- **Anchor heading:** `## Build and evidence`
- **Exact anchor line** (present at `934a667c`, line 106):

  ```text
  - User-visible changes require captioned video tied to the tested SHA.
  ```

- **Insert immediately AFTER that line** (new bullet, keep surrounding bullets untouched):

  ```text
  - Any user-visible UI change, including backend- or web-origin work, requires native iOS proof before `/ready`; canonical rule, evidence classes, and authority: `~/.codex/AGENTS.md` § Native iOS proof for user-visible UI changes (canonical).
  ```

- **Anchor check before applying:**

  ```bash
  grep -n "User-visible changes require captioned video tied to the tested SHA" AGENTS.md
  ```

## 2. `jleechanorg/worldai_frontend` — `CLAUDE.md`

- **File to edit:** `CLAUDE.md` (in that repo `AGENTS.md` is a symlink → `CLAUDE.md`; edit `CLAUDE.md` only).
- **Anchor heading:** `## Key Invariants`
- **Exact anchor line** (last line of the file):

  ```text
  - **Real Backend & LLM Verification**: Integration and UI verification must run against a real local or Cloud Run `mvp_site` backend and real LLM services without mock bypasses.
  ```

- **Insert immediately AFTER that line** (final bullet of `## Key Invariants`):

  ```text
  - **Native iOS Proof Before `/ready`**: Any user-visible UI change requires native iOS proof; canonical rule, evidence classes, and authority: `~/.codex/AGENTS.md` § Native iOS proof for user-visible UI changes (canonical).
  ```

- **Anchor check before applying:**

  ```bash
  grep -n "Real Backend & LLM Verification" CLAUDE.md
  ```

## Apply-time rules (for the paused downstream step)

1. Re-verify each anchor grep above first; anchors are line positions, not guarantees. If an anchor is
   missing, stop and report — do not guess a new location.
2. Two separate PRs, one per repository; do not batch them with unrelated worktree changes.
3. Diff size is non-production (docs-only) in both repos; no CI-wait requirement, but run the anchor
   grep after editing and confirm the symlink direction was not replaced by a regular file
   (`ls -la AGENTS.md CLAUDE.md`).
4. Neither edit may add numeric thresholds, gate definitions, or evidence-class lists — pointer only.

## Explicit non-authority statement

This note only points at the canonical section; it adds no gates, numeric thresholds, or evidence
classes, and it creates no broader merge authority.
