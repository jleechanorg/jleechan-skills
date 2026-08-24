---
description: Investigate dice integrity warnings for a campaign (your-project.com only — queries GCP project worldarchitecture-ai and the dice service).
type: llm-orchestration
execution_mode: immediate
---
> **Worldai-only command.** Hardcoded to the your-project.com GCP project
> (`worldarchitecture-ai`), the worldai dice service, and the
> `$PROJECT_ROOT/world_logic.py` injection path. The repo-local counterpart
> lives at
> `$GITHUB_REPOSITORY/.claude/commands/investigatedice.md`
> (currently a thin pointer to this file). When invoked outside the
> worldai repo, the GCP queries will fail.

## EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, execute these steps immediately.**
**This is NOT documentation - these are COMMANDS to execute right now.**

## Usage
```
/investigatedice <campaign_id_or_url> [service_name]
```

- `campaign_id_or_url`: A campaign ID (e.g., `OZTbL5nJ4tDWqAAVQmPr`) or a full game URL (the campaign ID will be extracted from the last path segment)
- `service_name` (optional): Cloud Run service name. Defaults to `mvp-site-app-s3` (preview). Use `mvp-site-app` for production.

## EXECUTION WORKFLOW

### Phase 1: Extract Campaign ID

Parse the argument. If it's a URL like `https://mvp-site-app-s3-i6xf2p72ka-uc.a.run.app/game/ABC123`, extract `ABC123` as the campaign ID.

### Phase 2: GCP Logs (parallel)

Run these GCP log queries in parallel using Bash:

**Query A - Dice enforcement & fabrication logs (last 4 hours):**
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="<service_name>" AND (textPayload=~"DICE-s8u" OR textPayload=~"CODE_EXEC_NO_RNG" OR textPayload=~"dice_fabrication" OR textPayload=~"dice_integrity") AND textPayload=~"<campaign_id>"' --limit=20 --freshness=4h --format='value(textPayload)' --project=worldarchitecture-ai
```

**Query B - System warnings for this campaign (last 4 hours):**
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="<service_name>" AND textPayload=~"SYSTEM WARNING" AND textPayload=~"<campaign_id>"' --limit=10 --freshness=4h --format='value(textPayload)' --project=worldarchitecture-ai
```

### Phase 3: Firestore Query

Write a temporary Python script to the scratchpad directory and execute it. The script should:

1. Initialize Firebase with clock skew patch:
```python
import os, sys, json
os.environ.setdefault("WORLDAI_DEV_MODE", "true")
sys.path.insert(0, "<project_root>")
from mvp_site.clock_skew_credentials import apply_clock_skew_patch
apply_clock_skew_patch()
import firebase_admin
from firebase_admin import credentials, firestore
if not firebase_admin._apps:
    cred = credentials.Certificate(os.path.expanduser("~/serviceAccountKey.json"))
    firebase_admin.initialize_app(cred)
db = firestore.client()
```

2. Find the campaign owner using collection group query on `campaigns` collection.

3. Query last 5 gemini story entries (sorted by timestamp DESC) and extract:
   - `debug_info.code_execution_used`
   - `debug_info.rng_verified`
   - `debug_info.code_contains_rng`
   - `debug_info.executed_code` (show first 500 chars per block)
   - `debug_info.stdout` (show first 300 chars)
   - `debug_info._dice_fabrication_correction`
   - `debug_info.dice_strategy`
   - `structured_fields.system_warnings`
   - `structured_fields.dice_metadata`
   - `structured_fields.action_resolution.mechanics.rolls`

4. Query `game_states/current_state` and extract:
   - `player_turn`
   - `pending_system_corrections`
   - `combat_state` (in_combat, combat_phase, rewards_processed)

Run with: `WORLDAI_DEV_MODE=true PYTHONPATH=<project_root> <venv>/bin/python <script_path>`

### Phase 4: Diagnosis Report

Present findings in a structured table:

```markdown
## Dice Investigation: <campaign_id>

### Campaign Info
| Field | Value |
|-------|-------|
| Campaign ID | ... |
| Title | ... |
| User ID | ... |
| Current Turn | ... |
| Service | ... (s3/prod) |

### Recent Turns - Code Execution Evidence
| Turn/Doc | code_exec_used | rng_verified | code_contains_rng | Strategy | Fabrication? |
|----------|----------------|--------------|-------------------|----------|-------------|
| ... | ... | ... | ... | ... | ... |

### Game State
- pending_system_corrections: ...
- combat_state: ...

### GCP Log Findings
- DICE-s8u enforcement count: ...
- CODE_EXEC_NO_RNG count: ...
- Recent warnings: ...

### Root Cause Analysis
<Diagnosis based on evidence>

### Recommendations
<What to do next>
```

### Phase 5: Check Deployed Version

Identify which commit/PR is deployed on the target service:
```bash
gcloud run services describe <service_name> --region=us-central1 --project=worldarchitecture-ai --format='value(spec.template.metadata.annotations["client.knative.dev/user-image"])'
```

Compare against known PR branches to determine if relevant fixes are deployed.

## Key Reference Files

| File | Purpose |
|------|---------|
| `$PROJECT_ROOT/dice_integrity.py` | Fabrication detection logic |
| `$PROJECT_ROOT/llm_providers/gemini_code_execution.py` | Code execution evidence extraction, AST-based RNG detection |
| `$PROJECT_ROOT/world_logic.py:4300-4320` | Correction injection into pending_system_corrections |
| `$PROJECT_ROOT/llm_service.py:4751-4757` | Pop corrections before compaction |
| `.claude/skills/dice-authenticity-standards.md` | Chi-squared testing, evidence fields |
| `.claude/skills/dice-roll-audit.md` | Campaign audit workflow |
| `scripts/audit_dice_rolls.py` | Full dice distribution audit script |

## Common Patterns

### Pattern: Gemini skips code_execution entirely
- **Symptom**: `code_execution_used: False` with dice rolls in action_resolution
- **Cause**: Model decided not to use code_execution tool despite instruction
- **Fix**: Correction injection tells model to use code_execution next turn

### Pattern: Code runs but no RNG detected
- **Symptom**: `code_execution_used: True`, `rng_verified: False`, `code_contains_rng: False`
- **Cause**: Model imported `random` but used `print()` with hardcoded values
- **Fix**: AST parser correctly rejects; correction injected

### Pattern: Missing dice_integrity field
- **Symptom**: `LLM_MISSING_FIELDS: Response missing ['dice_integrity']`
- **Cause**: Model didn't include dice_integrity in JSON response
- **Fix**: Server adds warning; not a code_execution issue

### Pattern: Stale combat_phase warnings
- **Symptom**: `REWARDS_STATE_WARNING` when combat ended turns ago
- **Cause**: `combat_phase: "ended"` persists after combat ends
- **Fix**: PR #4856 (dice_rng) adds stale combat detection
