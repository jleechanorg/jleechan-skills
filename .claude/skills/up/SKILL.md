---
name: up
description: "Use when the user invokes /up or asks to persist a coding-agent rule or preference. Default: repo-level Markdown under the active repo. Use /up --repo for any repo, /up --global for the cross-runtime surfaces."
---

# Update Coding-Agent Instructions

## Core contract

**Default scope is the active repo, not `~/.claude/`.** A rule lives in the
repo's Markdown files (CLAUDE.md / AGENTS.md / README.md / docs/**) where it
naturally applies — with one canonical copy and tight cross-references,
*not* scattered duplicates. The cross-runtime `~/.claude/CLAUDE.md` family is
reached only when a rule must apply across every coding-agent surface in
every session, or when the operator passes `--global`.

## Flags

- `/up` — **default**, edit the active repo's Markdown files only.
- `/up --repo <path>` — explicit repo override (when called from outside a repo).
- `/up --global` — full cross-runtime rewrite of the `~` surfaces
  (legacy behavior; rare).
- `/up --both` — repo **plus** the narrowest needed `~/.claude/CLAUDE.md`
  pointer (the common "this rule is repo-canonical but also useful globally"
  case). The repo file gets the full text; the `~` file gets a
  one-line pointer that names the repo owner.

## Workflow

1. Read the proposed instruction; search the *active repo's* Markdown
   (`<repo>/CLAUDE.md`, `<repo>/AGENTS.md`, `<repo>/README.md`, plus any
   existing sub-doc) for the distinctive concepts. Don't search `~` first
   unless `--global` was passed — the repo is the natural owner for most
   rules, and editing `~` doesn't help anyone who clones your repo.
2. Choose the narrowest owner in this order (first match wins):
   - Repo behavior (one repo, scope = this worktree): `<repo>/CLAUDE.md`,
     `<repo>/AGENTS.md`, or `<repo>/README.md` — pick whichever the repo
     already uses (look at file mtime + history of edits; if the repo has
     CLAUDE.md, prefer it; some repos use only AGENTS.md).
   - Multi-step workflow with thresholds / examples / reusable judgment:
     a directory-form `skills/<name>/SKILL.md` *inside the repo* under
     `.claude/skills/...` or the repo's own skills dir; check what the
     repo already does.
   - Cross-runtime invariant needed in every session across machines:
     canonical copy in `~/.claude/CLAUDE.md` with concise pointers elsewhere.
     This is the *fallback*, not the default.
   - Runtime-only behavior: only that runtime's surface.
3. Back up the target file before editing. Update the canonical copy once.
   If `--both`, add a one-line pointer in the `~` file at the right rule
   spot — never duplicate the body.
4. Keep slash commands as thin dispatchers to skills. Update Hermes
   resolver metadata only when command routing changes.
5. Machine-local content: never touch per-machine files in another
   machine's home; if a rule is non-machine-specific, sync the same
   ownership structure through `/mac` or `/linux`. Report unreachable hosts.

## Repo-Markdown catalog (default surfaces)

| Repo surface | When |
|---|---|
| `<repo>/CLAUDE.md` | Repo-scoped rules, machine-local safety, methodology. AGENTS.md symlinks here in many Claude Code setups — write through the symlink target. |
| `<repo>/AGENTS.md` | The newer/orchestrator-agnostic sibling; standalone (not a symlink) on Codex-driven repos. |
| `<repo>/README.md` | User-facing summary; only editable if the rule is genuinely user-visible (rare — behavior rules belong in CLAUDE.md/AGENTS.md). |
| `<repo>/docs/<topic>.md` | Long-form docs (architecture, runbooks, design), referenced from CLAUDE.md. |

If the repo already has both `CLAUDE.md` and `AGENTS.md` and they
disagree, the behavior that already worked is the canonical copy. Add a
cross-reference rather than rewriting both.

## Cross-runtime surfaces (only when `--global` or `--both`)

| Runtime | Surface |
|---|---|
| Claude | `~/.claude/CLAUDE.md` |
| Codex | `~/.codex/AGENTS.md` |
| Gemini | `~/.gemini/GEMINI.md` |
| Cursor | `~/.cursor/rules/env-preferences.mdc` |
| Hermes | `~/.hermes/workspace/SOUL.md`, only for Hermes behavior |
| Hermes routing | `~/.hermes/skills/RESOLVER.md`, only for command or skill routing |

## Brief-report contract (operational table goes in Markdown, not chat)

When `/up` writes or updates instructions, **produce a brief Markdown
report** (default location: `<active-repo>/roadmap/up-changelog-<YYYYMMDD-HHMM>.md`,
or `~/roadmap/up-changelog-<YYYYMMDD-HHMM>.md` for `--global`). The table
must stay short:

| Surface | Status | One-line reason |

Three columns, one row per touched surface. No prose, no captured-chat —
the file IS the receipt. **Do not dump the full table into the chat
reply.** A two-line pointer in chat is enough.

## Verification

- Grep the *canonical* surface (and pointers, if any) for the distinctive
  phrase. There must be exactly one full semantic copy.
- Confirm every pointer exists in the targeted runtime files.
- After changing a skill, verify YAML frontmatter begins with `---`.
- Smoke `codex debug prompt-input` when available.
- Run the managed-file tests; brief report file is the only deliverable.

## Common failure

Editing all surfaces "for consistency" creates semantic copies that drift.
Consistency = shared ownership + scoped overrides, not repeated prose.
Worse: editing `~/.claude/CLAUDE.md` for a repo-specific rule means the
rule lives in your home directory but applies only to one repo — anyone
cloning the repo gets no instructions, anyone forking your home gets
instructions about the wrong repo. Repo scope is the safe default.
