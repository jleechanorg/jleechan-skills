---
description: /repro_copy - copy a real campaign to the test user and replay the issue against a real local server + real LLM
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
When this command is invoked, execute the repro-copy workflow immediately.

## Required workflow

1. Read `.claude/skills/repro-copy.md`. For shared env (WORLDAI_DEV_MODE, credentials) see **`.claude/skills/repro-twin-clone-evidence/SKILL.md`** §1; the optional five-class harness is §5 in that file only.
2. Resolve the source campaign ID and the issue description from `$ARGUMENTS`.
3. Prefer:

```bash
./vpython scripts/repro_copy_campaign.py <campaign_id> --issue "<issue description>" --start-local
```

4. If the user supplied exact replay text, pass `--user-input "<text>"`.
5. Only pass `--delete-last-scene` when the operator explicitly asked for the
   variant mutation, and pair it with `--force-delete-last-scene`.
6. Save and report:
   - canonical campaign ID
   - variant campaign ID
   - replay input
   - evidence bundle path
7. Enforce user-scope evidence standards:
   - `~/.claude/skills/evidence-standards/SKILL.md`
   - `~/.claude/skills/evidence-standards/tmux-video-evidence.md`
   - `~/.claude/skills/evidence-standards/ui-video-evidence.md`

## Purpose

`/repro_copy` creates one canonical campaign copy and one variant copy for
determinism checks, then replays the same issue input against both copies using
the real local server and real LLM path.

## Examples

```bash
/repro_copy b9LPKcLHEwvG4FGsQDpu "planning block missing after level-up prompt"
```

```bash
/repro_copy b9LPKcLHEwvG4FGsQDpu "duplicate response on continue" --user-input "I continue through the gate."
```
