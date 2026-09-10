# Shared `CLAUDE.md` / `AGENTS.md` setup

Verbatim copies of the user's home-directory Claude/Codex policy files plus the
runtime adapter that ties them together, captured on 2026-09-09 so the layout
can be reproduced on another machine.

## Files in this directory

| File | Source on this machine | What it is |
|------|------------------------|------------|
| `AGENTS.shared.md` | `~/.codex/AGENTS.md` | The **canonical shared global policy** loaded by every Codex/Claude session. Edit shared rules here once. |
| `CLAUDE.adapter.md` | `~/.claude/CLAUDE.md` | The thin Claude adapter that imports the shared policy via `@~/.codex/AGENTS.md`. |

## How the "shared file setup" wires together

Two runtimes, one source of truth:

```
~/.codex/AGENTS.md      ← canonical shared policy (Codex reads natively)
        │
        │ imported via
        ▼
~/.claude/CLAUDE.md     ← Claude Code adapter: "@~/.codex/AGENTS.md"
                         + Claude-specific additions only
```

### Why the indirection exists

- **Single source of truth.** Universal rules live in `~/.codex/AGENTS.md`. Both
  Codex (native load) and Claude Code (via `@` import) read it. No drift.
- **Adapter pattern.** Runtime-specific behavior lives in the adapter
  (`~/.claude/CLAUDE.md` adds Claude-only subagent rules, model routing,
  voice/calibration). Edit the adapter; the shared rules stay untouched.

## Reproducing this layout on a fresh machine

```bash
# 1. Bootstrap the shared policy (Codex reads it natively; Claude imports it).
mkdir -p ~/.codex
# write or symlink ~/.codex/AGENTS.md to this repo's setup/AGENTS.shared.md

# 2. Write the Claude adapter (~/.claude/CLAUDE.md).
mkdir -p ~/.claude
cat > ~/.claude/CLAUDE.md <<'EOF'
# Claude Global Baseline
Shared policy is loaded below. Edit universal rules in `~/.codex/AGENTS.md`; keep only Claude-specific additions in this adapter.

@~/.codex/AGENTS.md
EOF
# then add Claude-only sections below the import
```

## Editing guidance (per `~/.codex/AGENTS.md`)

> Edit shared policy or runtime adapters — semantic signoff + behavioral gate (mandatory)
> Structural checks are necessary but not sufficient. For edits that shorten, move,
> or restructure a rule, ask whether an agent reading only the new text would still
> take the enforcement action; if unsure, do not ship. Keep high-salience autonomy
> and safety headings standalone. Before and after edits, run canaries: with an
> obviously implied next step and no blocker, does the agent proceed without
> asking, and does it cite the source before asserting a status claim?

Treat that gate as live for any edit to any file in this directory.

## Maintenance

- **Source of truth:** the files in this repo's `setup/` are a **snapshot** of
  what the user's home directory contained on 2026-09-09. They are useful for
  bootstrapping a new machine or reviewing the policy layout, not as a live
  mirror.
- **To refresh:** re-copy from the home directory, then commit. Do not edit the
  files in this directory in place — edit the home-directory originals and
  re-copy.
