# /nextsteps — Situational Assessment & Roadmap Update

## Purpose
Assess current session context, find relevant beads issues and roadmap docs, then update or create them to reflect new information. Use subagents for parallel work.

## Input
Optional: brief description of what just happened or what to assess. If omitted, assess from git log, beads status, and recent session context.

## Execution Steps

### Phase 0 — Gather context (parallel)
Run these in parallel:
1. `git log --oneline -10` — recent commits
2. `br list --status open` — open beads issues
3. `ls roadmap/` — available roadmap docs
4. `git diff HEAD~3..HEAD --stat` — what changed recently

### Phase 1 — Assess
Based on gathered context and any provided input:
- Identify themes (bug fixes, new features, infrastructure changes, policy updates)
- Match themes to existing beads issues or roadmap docs
- Identify gaps: what's missing from the issue tracker or roadmap

### Phase 2 — Update/Create (parallel subagents)
For each identified update, dispatch in parallel:

**Beads updates** (for each relevant open issue):
```bash
br update <id> --status <new_status>
br show <id>  # verify before updating
```

**New beads issues** (for gaps not tracked):
```bash
br create "<title>" --type <task|bug|feature|chore> --priority <0-4> --description "<details>"
```

**Roadmap doc updates** (edit existing `roadmap/*.md`):
- Add new decisions, findings, or status to relevant docs
- Keep updates concise — append, don't rewrite

**New roadmap docs** (for new initiatives):
- Create `roadmap/<TOPIC>.md` following existing doc style
- Include: Background, Current Status, Next Steps, Open Questions

### Phase 3 — Report
Summarize:
- Issues updated/created (with IDs)
- Docs updated/created (with paths)
- Recommended next actions
