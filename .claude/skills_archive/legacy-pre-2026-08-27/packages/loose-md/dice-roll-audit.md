# Dice Roll Audit - Campaign Analysis

## Overview
This skill documents how to audit dice rolls from Your Project campaigns. Use this to analyze dice roll fairness, detect anomalies, and validate game mechanics.

## Quick Start

### Audit a Campaign by ID
```bash
WORLDAI_DEV_MODE=true python scripts/audit_dice_rolls.py <campaign_id>
```

### Example
```bash
# Audit campaign from URL: https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/game/tAE30bFvyfO0rUd9cgyv
WORLDAI_DEV_MODE=true python scripts/audit_dice_rolls.py tAE30bFvyfO0rUd9cgyv
```

## What It Analyzes

### Dice Distribution
- Total rolls by die type (d4, d6, d8, d10, d12, d20, d100)
- Mean vs expected mean (fairness check)
- Standard deviation
- Distribution of roll values

### Anomaly Detection
- **Impossible values**: Rolls outside valid range (e.g., 0 or 21+ on d20)
- **Suspicious patterns**: Unusual clustering at high/low ends
- **Statistical deviation**: Significant variance from expected distribution

### Data Sources
The script extracts dice from:
1. **structured_fields**: Dice logged in tool calls and combat data
2. **text_pattern**: Dice mentioned in narrative text (e.g., "rolled a 15")

### Evidence Precedence & Parsing Rules
- **Primary sources**: `dice_audit_events` and `debug_info.tool_results` (authoritative).
- **Fallback**: `debug_info.stdout` JSON from Gemini code_execution (used only when no primary sources exist).
- **Legacy**: `dice_rolls` strings and narrative text patterns (only when structured sources are missing).
- **Distribution math**:
  - Uses **individual_rolls** when available (e.g., `[3, 5]` for `2d6`).
  - Falls back to parsed totals only when raw rolls are unavailable.
  - Totals with modifiers can distort fairness checks, so prefer roll arrays when present.

## Output Example

```
============================================================
CAMPAIGN DICE ROLL AUDIT
============================================================
Campaign ID: tAE30bFvyfO0rUd9cgyv
Campaign Title: alexiel swtor
User ID: vnLp2G3m21PJL6kxcuAqmWSOtm73
============================================================

Total story entries: 498
Entries with dice rolls: 66
Total dice rolls found: 93

--- d20 Analysis ---
Total rolls: 89
Range: 0 - 23
Mean: 7.73 (expected: 10.50)
Deviation: -2.77
Std Dev: 5.41
Distribution: {0: 2, 1: 2, 2: 10, 3: 9, ...}

 WARNINGS:
  - Impossible values detected: [0, 21, 22, 23]
```

## How to Get Campaign ID

From a game URL like:
```
https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/game/tAE30bFvyfO0rUd9cgyv
```
The campaign ID is the last segment: `tAE30bFvyfO0rUd9cgyv`

## Prerequisites

### Environment Variables
```bash
export WORLDAI_DEV_MODE=true
export WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json
```

### Service Account Key
Location: `~/serviceAccountKey.json`
Project: `worldarchitecture-ai`

## Understanding Results

### Expected Means by Die Type
| Die  | Expected Mean |
|------|---------------|
| d4   | 2.5           |
| d6   | 3.5           |
| d8   | 4.5           |
| d10  | 5.5           |
| d12  | 6.5           |
| d20  | 10.5          |
| d100 | 50.5          |

### Warning Indicators
- **Impossible values**: Indicates parsing issues or modifier inclusion in totals
- **High deviation (>2)**: May indicate unfair RNG or data extraction issues
- **All text_pattern source**: No structured dice logging - may need improvement

### Chi-Squared Authenticity Check

The audit now includes chi-squared testing for dice authenticity:

| Chi-Squared | Verdict |
|-------------|---------|
| < 30 | PASS - Normal random variation |
| 30-50 | WARNING - Minor anomaly |
| 50-100 | FAIL - Significant deviation |
| > 100 | FAIL - Likely fabrication |

**Reference case**: PR #2551 detected fabrication with chi-squared = 411.81

See `dice-authenticity-standards.md` for full chi-squared methodology and RNG verification standards.

## Troubleshooting

### Clock Skew Error
```
ValueError: WORLDAI_GOOGLE_APPLICATION_CREDENTIALS requires WORLDAI_DEV_MODE=true
```
**Solution:** Set `WORLDAI_DEV_MODE=true` before running

### No Dice Found
If "No dice rolls found", possible causes:
1. Campaign doesn't use D&D 5e mechanics
2. Dice rolls not stored in structured_fields
3. Narrative text doesn't contain dice notation

### Invalid JWT Error
The script automatically applies clock skew patch. If still failing, check:
- Service account key validity
- System clock accuracy

## GCP Cloud Logging

All dice rolls executed via the tool system are now logged to GCP Cloud Logging with the prefix `DICE_AUDIT:` and `DICE_TOOL_RESULT:`.

### Log Format Examples
```
DICE_AUDIT: notation=1d20+5 | rolls=[15] | modifier=5 | total=20 | nat20=False | nat1=False
DICE_TOOL_EXEC: tool=roll_attack | args={'attack_modifier': 5, 'target_ac': 15}
DICE_TOOL_RESULT: tool=roll_attack | weapon=Longsword | rolls=[12] | total=17 | hit=True | critical=False | damage=8
```

### Searching GCP Logs
```bash
# Find all dice rolls in last hour
gcloud logging read "textPayload:DICE_AUDIT" --limit=100 --freshness=1h

# Find all dice tool executions
gcloud logging read "textPayload:DICE_TOOL_EXEC" --limit=50
```

## Script Location
`scripts/audit_dice_rolls.py`

## Related Skills
- `dice-authenticity-standards.md` - Chi-squared testing and RNG verification
- `dice-real-mode-tests.md` - MCP real-mode testing
- `firebase-prod-campaigns.md` - Querying campaign data
- `worldai-mcp-server-usage.md` - MCP server interaction
