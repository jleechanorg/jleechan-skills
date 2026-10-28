---
name: up
description: "Use when the user invokes /up or asks to persist a coding-agent rule or preference. Default: repo-level Markdown under the active repo. Use /up --repo for any repo, /up --global for the cross-runtime surfaces."
---

# Update Coding-Agent Instructions

## Core contract

**Default scope is the active repo, not `~/.claude/`.** A rule lives in the
repo's Markdown files (CLAUDE.md / AGENTS.md / README.md / docs/**) where it
naturally applies — with one canonical copy and tight cross-references,
*not* scattered duplicates. The shared cross-runtime `~/.codex/AGENTS.md` owner is
reached only when a rule must apply across every coding-agent surface in
every session, or when the operator passes `--global`.

## Flags

- `/up` — **default**, edit the active repo's Markdown files only.
- `/up --repo <path>` — explicit repo override (when called from outside a repo).
- `/up --global` — update the narrow shared owner or runtime adapter required by
  the request; it is not a blanket rewrite of every runtime surface.
- `/up --both` — repo **plus** the narrowest needed `~/.codex/AGENTS.md`
  pointer (the common "this rule is repo-canonical but also useful globally"
  case). The repo file gets the full text; the `~` file gets a
  one-line pointer that names the repo owner.

## Workflow

1. Read the proposed instruction; inspect both the home owner and active repo's Markdown
   (`<repo>/CLAUDE.md`, `<repo>/AGENTS.md`, `<repo>/README.md`, plus any
   existing sub-doc) for the distinctive concepts. Resolve declared ownership
   before editing; repo-specific rules remain in their repository.
2. Choose the narrowest owner in this order (first match wins):
   - Repo behavior (one repo, scope = this worktree): `<repo>/CLAUDE.md`,
     `<repo>/AGENTS.md`, or `<repo>/README.md` — pick whichever the repo
     declares as owner, resolving any symlink/import and checking current content.
     A newer mtime alone does not establish authority.
   - Multi-step workflow with thresholds / examples / reusable judgment:
     a directory-form `skills/<name>/SKILL.md` *inside the repo* under
     `.claude/skills/...` or the repo's own skills dir; check what the
     repo already does.
   - Cross-runtime invariant needed in every session across machines:
     canonical copy in `~/.codex/AGENTS.md`; Claude imports it through
     `~/.claude/CLAUDE.md`. Keep runtime-only rules in their own adapters.
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

If the repo has both `CLAUDE.md` and `AGENTS.md`, resolve their declared scope,
symlink/import relationship and current owner. Reconcile a real contradiction
at that owner; prior apparent success does not establish instruction authority.

## Cross-runtime surfaces (only when `--global` or `--both`)

| Runtime | Surface |
|---|---|
| Claude | `~/.claude/CLAUDE.md` |
| Codex | `~/.codex/AGENTS.md` |
| Gemini | `~/.gemini/GEMINI.md` |
| Cursor | `~/.cursor/rules/env-preferences.mdc` |
| Hermes | `~/.hermes/workspace/SOUL.md`, only for Hermes behavior |
| Hermes routing | `~/.hermes/skills/RESOLVER.md`, only for command or skill routing |


## Reference - authoritative sources (researched 2026-10-12)

- **Claude Code memory docs**: https://code.claude.com/docs/en/memory (updated 2026-10-08) - load order: managed policy -> user (`~/.claude/CLAUDE.md`) -> project (`./CLAUDE.md` or `./.claude/CLAUDE.md`); Claude Code can read a repo's `AGENTS.md` in place of CLAUDE.md.
- **`@` import semantics** (same page, "Import additional files"): `@path/to/file` expands into context at launch; relative paths resolve against the **importing file**, not the cwd; recursive imports cap at **4 hops**; spaces need backslash escapes; code spans/fences are skipped. Imports do **not** reduce context cost.
- **Sizing/scoping**: target **under 200 lines** per CLAUDE.md; prefer path-scoped `.claude/rules/` (load only for matching files) over imports; run `/doctor prompt-audit` (v2.1.283+) to find stale/conflicting instructions.

## Brief-report contract (operational table goes in Markdown, not chat)

When `/up` writes or updates instructions, **produce a brief Markdown
report** under `~/roadmap/up-changelog-<YYYYMMDD-HHMM>.md` for every scope.
Durable agent-authored reports belong in `~/roadmap/`, never a code repo's
roadmap directory. The table
must stay short:

| Surface | Status | One-line reason |

Three columns, one row per touched surface. No prose, no captured-chat —
the file IS the receipt. **Do not dump the full table into the chat
reply.** A two-line pointer in chat is enough.

## Instruction consistency contract

- **Outcome:** Active instructions lead agents through authorized work to its verified result without conflicting owners or premature handoffs.
- **Non-goals:** No new runtime code, credentials, paid capacity, unrelated task authority, or weakening of explicit approval and repository-specific gates.
- **Acceptance:** Each confirmed active conflict is reconciled at its owner; references resolve; unrelated changes survive; installed copies are compared before synchronization.
- **User story:** An operator asks for work and the agent performs available reversible next steps, including reviews, instead of returning those steps as work for the operator.
- **Proof plan:** Inspect the complete before/after diff, run applicable structure checks and policy scenarios, and obtain the lifecycle's independent full-scope review before claiming approval.
- **Mock exemption:** Markdown instruction changes need no application UI mock; claimed application or agent runtime behavior still needs its own evidence.
- **Risk:** Shortening a rule can remove enforcement. Preserve standalone autonomy/safety headings and verify both continuation and genuine authority-boundary scenarios.

## Verification

- Grep the *canonical* surface (and pointers, if any) for the distinctive
  phrase. There must be exactly one full semantic copy.
- Confirm every pointer exists in the targeted runtime files.
- After changing a skill, verify YAML frontmatter begins with `---`.
- Smoke `codex debug prompt-input` when available.
- Run applicable existing managed-file checks. The brief report records the
  completed instruction changes; it does not replace them or their validation.

## Common failure

Editing all surfaces "for consistency" creates semantic copies that drift.
Consistency = shared ownership + scoped overrides, not repeated prose.
Worse: editing `~/.claude/CLAUDE.md` for a repo-specific rule means the
rule lives in your home directory but applies only to one repo — anyone
cloning the repo gets no instructions, anyone forking your home gets
instructions about the wrong repo. Repo scope is the safe default.
