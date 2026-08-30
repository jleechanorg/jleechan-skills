---
description: Orchestration roadmap command — captures session ideas, checks upstream repos for existing functionality, and creates/updates roadmap/ docs + beads
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately.**
**This is NOT documentation — these are COMMANDS to execute right now.**

## Purpose

`/roadmap_orch` (alias: `/roadmapo`) captures engineering ideas from the current session, checks two upstream repos to avoid duplicate work, and writes a roadmap doc + creates beads.

**Run this at the end of any session where new orchestration ideas were discussed.**

## Execution Workflow

### Step 1 — Extract ideas from this session

Reflect on the current conversation. Identify:
- New features discussed or proposed
- Gaps in the current system that were surfaced
- Bugs that were found (whether fixed or not)
- Architecture decisions that were made
- Anything that should be tracked as future work

List each idea with a one-line summary.

### Step 2 — Research upstream repos for existing functionality

For EACH idea, check these two upstream repos:

**A. ComposioHQ/agent-orchestrator (`~/projects_reference/agent-orchestrator/`)**
```bash
# Search for relevant capability
rg -l "<keyword>" ~/projects_reference/agent-orchestrator/src/ 2>/dev/null | head -5
rg -n "<keyword>" ~/projects_reference/agent-orchestrator/src/ 2>/dev/null | head -10
```

Key directories to check:
- `src/scm/` — GitHub SCM operations (merge, review, comments)
- `src/lifecycle-manager/` — session lifecycle, stuck/idle detection
- `src/session-manager/` — session state, reactions
- `ARCHITECTURE.md` — high-level capabilities

**B. openclaw/openclaw (upstream CLI)**
```bash
gh api repos/openclaw/openclaw/contents 2>/dev/null | python3 -c "import json,sys; [print(f['name']) for f in json.load(sys.stdin)]"
openclaw --help 2>/dev/null
openclaw agent --help 2>/dev/null
```

For each idea, record one of:
- `EXISTS_UPSTREAM` — capability already in openclaw or AO; use that instead of building
- `PARTIAL` — partial capability exists; gap identified
- `NEW` — genuinely new; proceed with implementation

### Step 3 — Determine roadmap doc target

Find the most relevant existing doc in `roadmap/` for the ideas discussed:
```bash
ls roadmap/*.md
```

If a doc clearly fits (e.g., `AGENTO_GREEN_LOOP_GAPS.md` for agento gaps), UPDATE it.
If no good fit exists, CREATE a new doc named `roadmap/<TOPIC>_DESIGN.md`.

### Step 4 — Write the roadmap doc

For each `NEW` or `PARTIAL` idea, add a section:

```markdown
### <Feature Name> (`<bead-id-if-exists>`)

**Status:** NEW | PARTIAL (what upstream has)
**Upstream check:** AO — <finding>. openclaw — <finding>.

<What the feature does, why we need it, what upstream is missing>

**Implementation approach:** <config vs Python vs bash, estimated complexity>
```

For `EXISTS_UPSTREAM` ideas, add a note redirecting to the upstream capability.

### Step 5 — Create beads for NEW/PARTIAL ideas

For each new idea not already tracked:
```bash
~/.cargo/bin/br create "<title>" -t <feature|bug|task> -p 1 -d "<description with upstream check result>"
```

Skip bead creation if a matching bead already exists (check `br list` first).

### Step 6 — Commit the roadmap update

```bash
git add roadmap/<updated-or-new-doc>.md
git commit -m "docs(roadmap): capture session ideas — <brief summary>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

Do NOT create a separate PR for roadmap-only doc changes — commit directly to the current branch.

### Step 7 — Report

Print a summary table:

| Idea | Status | Bead | Upstream |
|------|--------|------|----------|
| <idea> | NEW/PARTIAL/EXISTS | orch-xxxx | AO has X / openclaw has Y |

---

## Quick Reference — Upstream Capabilities

### ComposioHQ/agent-orchestrator (AO) — CONFIRMED EXISTING
| Capability | Location |
|-----------|----------|
| PR review thread detection | `src/scm/github.ts` |
| Auto-merge (`scm.mergePR()`) | `src/scm/` |
| Stuck/idle session detection | `src/lifecycle-manager/` |
| Session state reactions | `src/session-manager/` |
| CodeRabbit approval check | `src/session-manager/` |
| Spawn sessions for PRs | `ao spawn` CLI |

### jleechanclaw — BUILT (not in upstreams)
| Capability | Location |
|-----------|----------|
| Poke rate-limiting (60min) | `scripts/ao-backfill.sh` |
| CR comment-based approval fallback | `.claude/scripts/agento-report.sh` |
| launchd cron backfill scheduling | `launchd/` |

### Known Gaps (not in any repo)
| Gap | Bead |
|-----|------|
| Auto-resolve review threads (resolveReviewThread GraphQL) | `orch-1roe` |
| Auto-approval path (no reviewDecision bot) | `orch-uq4z` |
