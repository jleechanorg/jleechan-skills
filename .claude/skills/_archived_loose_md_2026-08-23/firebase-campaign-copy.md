# Firebase Campaign Copy - Production Data for Testing

## Overview
Copy production campaigns across users for testing without auth bypass, using Firebase Admin SDK.

## Prerequisites
```bash
export WORLDAI_DEV_MODE=true
export WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json
```

## Copy Campaign Script

**Location:** `scripts/copy_campaign.py`

**Features:**
- Cross-user campaign copying
- Auto-find source user by campaign ID
- Search campaigns by title
- Copies all subcollections (story, game_states, notes, characters)
- No auth bypass needed (uses service account)

## Usage Patterns

### 1. Copy by Campaign ID (Recommended)
```bash
# Auto-finds source user, copies to destination user
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/copy_campaign.py \
  --find-by-id JXXNfJpdqNtH60HN942q \
  --dest-user-id 0wf6sCREyLcgynidU5LjyZEfm7D2 \
  --suffix "(test copy)"
```

### 2. Copy by Title
```bash
# Searches all users for matching title
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/copy_campaign.py \
  --find-by-title "gaia julia v2" \
  --dest-user-id 0wf6sCREyLcgynidU5LjyZEfm7D2
```

### 3. Direct Copy (If You Know Source User)
```bash
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/copy_campaign.py \
  SOURCE_UID \
  SOURCE_CAMPAIGN_ID \
  --dest-user-id DEST_UID
```

## Find User UID by Email

**Use campaign_manager.py:**
```bash
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/campaign_manager.py find-user <your-email@gmail.com>
```

**Output:**
```
✅ Found user: <your-email@gmail.com>
🆔 Firebase UID: 0wf6sCREyLcgynidU5LjyZEfm7D2
```

## Example: Copy Production Campaign for Testing

**Scenario:** Copy campaign JXXNfJpdqNtH60HN942q from $USER@gmail.com to <your-email@gmail.com>

**Steps:**
```bash
# 1. Find destination user UID
WORLDAI_DEV_MODE=true python scripts/campaign_manager.py find-user <your-email@gmail.com>
# Output: 0wf6sCREyLcgynidU5LjyZEfm7D2

# 2. Copy campaign (auto-finds source user)
WORLDAI_DEV_MODE=true python scripts/copy_campaign.py \
  --find-by-id JXXNfJpdqNtH60HN942q \
  --dest-user-id 0wf6sCREyLcgynidU5LjyZEfm7D2 \
  --suffix "(test copy)"

# Output:
# ✅ Created new campaign: qwN7EwNqbJXnl5y3Npjj
# 📝 Name: gaia julia v2 (test copy)
#   ✅ Copied 362 documents from story
#   ✅ Copied 1 documents from game_states
```

## Script Output

**Success:**
```
✅ Created new campaign: qwN7EwNqbJXnl5y3Npjj
📝 Name: gaia julia v2 (test copy)
  ✅ Copied 362 documents from story
  ✅ Copied 1 documents from game_states

✅ Campaign copied successfully!
📋 Campaign ID: qwN7EwNqbJXnl5y3Npjj
💡 To access: Use your environment's base URL + /game/qwN7EwNqbJXnl5y3Npjj
```

## Repro: Copy Exact State at Bug-Report Time

When a bug is reported, **copy the campaign immediately** so the reproduction
uses the exact state at the time of report (not a later mutated state).

### Required Inputs
- **Campaign ID** from the report
- **Report timestamp (UTC)**
- **Destination user UID** (test account)

### Step-by-step
```bash
# 1) Copy the campaign immediately (preserves all fields + subcollections).
#    Use a timestamped suffix so we can trace the report state later.
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/copy_campaign.py \
  --find-by-id <CAMPAIGN_ID> \
  --dest-user-id <DEST_UID> \
  --suffix "(bug report 2026-02-02T02:03Z)"

# Output includes the new campaign ID:
# ✅ Created new campaign: <NEW_CAMPAIGN_ID>

# 2) Capture the copied game state for reproducibility.
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/fetch_campaign_gamestate.py <NEW_CAMPAIGN_ID>

# 3) Export the story log for context (optional but recommended).
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/download_campaign.py --uid <DEST_UID> \
  --campaign-id <NEW_CAMPAIGN_ID> --output-dir /tmp/your-project.com/bug_repros
```

### Notes
- **Timing matters**: copying later will lose the exact report state.
- **Title suffix** should include the report timestamp for traceability.
- Use the **copied** campaign ID for all repro tests to avoid mutating the original.

## Use Cases

1. **Testing with Production Data**
   - Copy large campaigns to test accounts
   - Validate caching behavior with real story history
   - Test payload equivalence across servers

2. **User Data Migration**
   - Move campaigns between accounts
   - Backup campaigns before testing

3. **Campaign Duplication**
   - Create campaign variants for testing
   - Preserve original while experimenting

## Technical Notes

- **Collection Group Query:** Uses efficient Firestore collection group query to find campaigns across all users
- **Subcollections:** Automatically copies all subcollections (story, game_states, notes, characters)
- **Field Preservation:** Copies all fields including timestamps without modification
- **Document IDs:** Preserves original document IDs in subcollections for ordering
- **No Auth Bypass:** Uses Firebase Admin SDK service account (no testing shortcuts)

## Reference

**See also:**
- `scripts/campaign_manager.py` - Query campaigns, analytics, deletion
- `scripts/CLAUDE.md` - Full Firebase operations documentation
- `.claude/skills/firebase-prod-campaigns.md` - Production campaign queries
