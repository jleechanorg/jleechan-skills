---
description: /usage Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute Documented Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps sequentially.

## 📋 REFERENCE DOCUMENTATION

# /usage Command

Check Claude API usage and rate limits along with git status.

## Usage

```
/usage
```

## Description

Shows git branch and PR status for context. (API usage reporting was never
implemented — see note below.)

## Implementation

**Single Command**: `~/.claude/hooks/git-header.sh`

Falls back to the canonical `~/.claude/hooks/git-header.sh` path when the cwd
is not a git repo (`git rev-parse --show-toplevel` fails outside a repo).

**Note (verified 2026-07-14):** `git-header.sh` has NO `--with-api` or
`--monitor` flags and contains no API-usage logic (grep for `with-api`, `API`,
`usage`, `remaining` returns zero matches). The previously documented
`[API: <remaining>/50 requests ...]` output line, reset times, and threshold
alerts do not exist. For real usage/rate-limit data, use the built-in Claude
Code `/usage` TUI screen or `npx ccusage`.

## Output Format

```
[Local: <branch> | Remote: <upstream> | PR: <number> <url>]
```
