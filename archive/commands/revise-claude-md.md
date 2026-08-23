---
description: Update CLAUDE.md with learnings from this session
type: llm-orchestration
execution_mode: immediate
allowed-tools: Read, Edit, Glob
---

Update CLAUDE.md with learnings from this session. Review what context was missing that would have helped future Claude sessions work more effectively.

Source: adapted from anthropics/claude-plugins-official/claude-md-management

## Step 1: Reflect on Session Learnings

What context was missing or discovered that would help future sessions?

- Bash commands discovered or used frequently
- Code style patterns followed in this project
- Testing approaches that worked (or failed)
- Environment/configuration quirks (Firebase, Cloud Run, Gunicorn, etc.)
- Warnings, gotchas, or foot-guns encountered
- CLAUDE.md rules that were unclear or needed clarification
- New tools, MCP integrations, or patterns added

## Step 2: Find CLAUDE.md Files

Use the Glob tool to find CLAUDE.md files in this project:

```
Glob pattern: **/CLAUDE.md
```

Decide where each addition belongs:
- `./CLAUDE.md` — Team-shared project rules (checked into git)
- `.claude.local.md` — Personal/local session notes only (consider adding to your local .gitignore if not already present)

**COMPACTNESS RULE**: Root CLAUDE.md must stay under 200 lines. Move detailed content to `.claude/skills/*.md` and add a reference.

## Step 3: Draft Additions

Keep each addition concise — one line per concept. CLAUDE.md is injected into every prompt, so brevity matters.

Format: `<command or pattern>` — `<brief description>`

Avoid:
- Verbose explanations already covered elsewhere
- Obvious things any senior engineer knows
- One-off fixes unlikely to recur

## Step 4: Show Proposed Changes

For each proposed addition, show:

```
### Update: ./CLAUDE.md (or .claude/skills/[file].md)

**Why:** [one-line reason this helps future sessions]

\`\`\`diff
+ [the addition — keep it brief]
\`\`\`
```

## Step 5: Apply with Approval

Ask the user which proposed changes to apply. Only edit files they explicitly approve.

When editing, use the Edit tool (not Write) to make targeted additions. Never delete existing CLAUDE.md content unless the user explicitly requests removal. Never modify CLAUDE.md rules unrelated to session learnings.
