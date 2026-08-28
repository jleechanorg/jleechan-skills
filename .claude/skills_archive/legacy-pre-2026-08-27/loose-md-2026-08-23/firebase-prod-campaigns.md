---
name: firebase-prod-campaigns
description: How to read production campaigns from Firestore — UID resolution, nested path, firestore_service shortcut, repro_copy flags
when_to_use: Whenever fetching a campaign by ID, looking up a user in Firestore, or running repro_copy_campaign.py against a production campaign
triggers:
  - fetch campaign from firestore
  - get campaign by id
  - campaign not found firestore
  - production campaign lookup
  - source user id repro
allowed-tools: Bash, Read
---

# Firebase Production Campaign Database Access

## Overview
This skill documents how to query the **production Firestore database** for Your Project campaigns and user data.

## CRITICAL: UID first, then campaign path

**Never pass email to `get_campaign_by_id`. Resolve UID first.**

```python
# Preferred — uses firestore_service which handles story fetch + clock skew
from mvp_site import firestore_service
import firebase_admin
from firebase_admin import auth, credentials
import os

cred = credentials.Certificate(os.path.expanduser('~/serviceAccountKey.json'))
try:
    firebase_admin.initialize_app(cred)
except ValueError:
    pass  # already initialized

uid = auth.get_user_by_email('<your-email@example.com>').uid
# → '<YOUR_UID>'

campaign, story = firestore_service.get_campaign_by_id(uid, '<CAMPAIGN_ID>')
initial_prompt = campaign.get('initial_prompt', '')  # up to 65KB
```

### repro_copy_campaign.py — always pass `--source-user-id`

Without it the script falls back to scanning users for the campaign owner, which
is slow, may hit permission limits on large projects, and ends in **ValueError**
if the campaign cannot be resolved—pass the UID whenever you have it.

```bash
# Suboptimal — owner scan instead of a direct path:
./vpython scripts/repro_copy_campaign.py <CAMPAIGN_ID> --issue "no initial spells"

# CORRECT — resolve UID first, then pass it:
UID=$(./vpython -c "
import firebase_admin; from firebase_admin import auth, credentials; import os
cred = credentials.Certificate(os.path.expanduser('~/serviceAccountKey.json'))
try: firebase_admin.initialize_app(cred)
except: pass
print(auth.get_user_by_email('<your-email@example.com>').uid)
")
[ -n "$UID" ] || { echo "UID lookup failed" >&2; exit 1; }
./vpython scripts/repro_copy_campaign.py <CAMPAIGN_ID> \
  --source-user-id "$UID" \
  --issue "no initial spells"
```

## CRITICAL: Campaign Lookup

**Campaigns are NESTED under users, NOT at root level!**

```python
# WRONG - This queries the wrong collection (test data only):
db.collection('campaigns').document('VqqJLpABua9bvAG4ArTg')

# CORRECT - Campaigns are nested under user UID:
db.collection('users').document(uid).collection('campaigns').document('VqqJLpABua9bvAG4ArTg')
```

### Quick Lookup for Known Campaign ID
```python
# 1. Get user UID from email
user_record = auth.get_user_by_email('$USER@gmail.com')
uid = user_record.uid  # e.g., '<YOUR_UID>'

# 2. Query nested path
doc = db.collection('users').document(uid).collection('campaigns').document('CAMPAIGN_ID').get()
```

## Database Structure

```
Firestore Database: worldarchitecture-ai
├── campaigns/                    # ← WRONG: Only test data here (5 campaigns)
│   └── {test_campaign_id}/
│
└── users/                        # ← CORRECT: Real user data here (146+ campaigns)
    └── {Firebase_Auth_UID}/      # e.g., <YOUR_UID>
        └── campaigns/
            └── {campaign_id}/    # e.g., VqqJLpABua9bvAG4ArTg
                ├── title         # "Nocturne post bg3 zhent"
                ├── created_at
                ├── last_played
                ├── world_name
                ├── game_states/              # ← SUBCOLLECTION for game state
                │   └── current_state/        # Main game state document
                │       ├── player_character_data
                │       ├── combat_state
                │       ├── npc_data
                │       └── custom_campaign_state/
                │           └── god_mode_directives[]  # ← Persisted rules
                └── story/
                    └── {entry_id}/
                        ├── actor (user/gemini)
                        ├── text
                        └── timestamp
```

## IMPORTANT: Game State Location

**Game state is in a SUBCOLLECTION, not a field!**

```python
# WRONG - game_state is NOT a field on the campaign document:
campaign = db.collection('users').document(uid).collection('campaigns').document(campaign_id).get()
game_state = campaign.to_dict().get('game_state')  # Returns empty!

# CORRECT - game_state is in a subcollection called 'game_states':
game_state_ref = db.collection('users').document(uid).collection('campaigns').document(campaign_id).collection('game_states').document('current_state')
game_state = game_state_ref.get().to_dict()
```

### Querying God Mode Directives

```python
# Get god mode directives for a campaign
game_state_ref = campaign_ref.collection('game_states').document('current_state')
game_state = game_state_ref.get().to_dict()

custom_campaign_state = game_state.get('custom_campaign_state', {})
god_mode_directives = custom_campaign_state.get('god_mode_directives', [])

for directive in god_mode_directives:
    if isinstance(directive, dict):
        print(f"Rule: {directive.get('rule')}")
        print(f"Added: {directive.get('added')}")
```

### Using the Directive Query Script

```bash
# List all directives for a campaign
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/query_directives.py wBoMKQuMnvLfyjTFTBHd

# Debug why a directive wasn't saved
python scripts/query_directives.py wBoMKQuMnvLfyjTFTBHd --debug-missing "power scaling"

# Manually add a missing directive
python scripts/query_directives.py wBoMKQuMnvLfyjTFTBHd --add "Level 9 is extremely powerful - never use 'mere' or 'modest'"
```

## Debugging Missing God Mode Directives

When a user's god mode request doesn't result in a saved directive, follow this process:

### 1. How Directives Are Saved

The LLM must return a `directives` field in its structured JSON response:

```json
{
    "god_mode_response": "Acknowledged...",
    "directives": {
        "add": ["Rule to remember going forward"],
        "drop": ["Rule to stop following"]
    }
}
```

**Processing code:** `$PROJECT_ROOT/world_logic.py:1585-1667`
**Prompt instructions:** `$PROJECT_ROOT/prompts/god_mode_instruction.md:72-96`

### 2. Common Failure Modes

| Symptom | Cause | Solution |
|---------|-------|----------|
| Directive acknowledged but not saved | LLM returned `god_mode_response` but no `directives.add` | Check raw LLM response |
| Directive in `dm_notes` only | LLM put rule in `state_updates.debug_info.dm_notes` | `dm_notes` are now injected into future prompts as part of the system prompt |
| Empty `god_mode_directives` list | No directives ever saved | Check story entries for god mode responses |

### 3. Debugging Process

```python
# 1. Check if directives exist
custom_state = game_state.get('custom_campaign_state', {})
directives = custom_state.get('god_mode_directives', [])
print(f"Saved directives: {len(directives)}")

# 2. Find god mode story entries
story_ref = campaign_ref.collection('story')
for entry in story_ref.order_by('timestamp', direction='DESCENDING').limit(100).stream():
    data = entry.to_dict()
    if data.get('actor') == 'gemini' and 'God Mode active' in data.get('text', ''):
        debug_info = data.get('debug_info', {})
        raw_response = debug_info.get('raw_response_text', '')
        if raw_response:
            parsed = json.loads(raw_response)
            print(f"Entry {entry.id}:")
            print(f"  Has directives field: {'directives' in parsed}")
            if 'directives' not in parsed:
                print(f"  State updates: {parsed.get('state_updates', {})}")
```

### 4. Key Insight: `dm_notes` vs `directives`

- **`dm_notes`**: Internal notes stored in `state_updates.debug_info.dm_notes`. ARE injected into future system prompts (as of this PR) to provide important context the LLM wrote but did not formally save as directives.
- **`directives`**: Persisted rules stored in `god_mode_directives[]`. ARE injected into system prompts via `agent_prompts.py:669-753`.

If the LLM writes to `dm_notes` instead of `directives`, the rule won't persist as a formal directive.

## User Identification
- Users are identified by **Firebase Auth UID**, NOT email
- Primary user: `<your-email@example.com>` → UID: `<YOUR_UID>`
- Test user: `<your-email@gmail.com>`
- Use `auth.get_user_by_email()` to convert email → UID

## Prerequisites

### Environment Variables
```bash
export WORLDAI_DEV_MODE=true
export WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json
```

### Service Account Key
Location: `~/serviceAccountKey.json`
Project: `worldarchitecture-ai`

## Using campaign_manager.py

The recommended tool for production queries is `scripts/campaign_manager.py`.

### Find User by Email
```bash
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/campaign_manager.py find-user $USER@gmail.com
```

### Analyze User Activity (with token/cost estimation)
```bash
# Analyze last 3 months
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/campaign_manager.py analytics $USER@gmail.com

# Specific month
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/campaign_manager.py analytics $USER@gmail.com --month 2025-11
```

### Query Campaigns by Name
```bash
WORLDAI_DEV_MODE=true \
WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=~/serviceAccountKey.json \
python scripts/campaign_manager.py query <UID> "Campaign Name"
```

## Direct Python Query (Ad-hoc)

For custom queries, use this pattern:

```python
import sys
sys.path.insert(0, 'mvp_site')

# CRITICAL: Apply clock skew patch BEFORE importing Firebase
from mvp_site.clock_skew_credentials import apply_clock_skew_patch
apply_clock_skew_patch()

import firebase_admin
from firebase_admin import auth, firestore, credentials
import os

# Initialize with explicit credentials
if firebase_admin._apps:
    firebase_admin.delete_app(firebase_admin.get_app())

cred = credentials.Certificate(os.path.expanduser('~/serviceAccountKey.json'))
firebase_admin.initialize_app(cred)
db = firestore.client()

# Find user by email
email = '$USER@gmail.com'
user_record = auth.get_user_by_email(email)
uid = user_record.uid

# Get campaigns
campaigns_ref = db.collection('users').document(uid).collection('campaigns')
for campaign in campaigns_ref.stream():
    data = campaign.to_dict()
    print(f"{campaign.id}: {data.get('title')}")

    # Get story entries
    story_ref = campaigns_ref.document(campaign.id).collection('story')
    entry_count = sum(1 for _ in story_ref.stream())
    print(f"  Entries: {entry_count}")
```

## Token/Cost Estimation Constants

From `$PROJECT_ROOT/llm_service.py`:
- **Base system instructions:** ~43,000 tokens
- **World content estimate:** ~50,000 tokens
- **Tokens per story entry:** ~500 tokens
- **Max history turns:** 100 (truncation limit)
- **200K threshold:** Above this = "long context" pricing (2x cost)

### Gemini 3 Flash Pricing
| Context Size | Input | Output |
|--------------|-------|--------|
| ≤200K tokens | $0.50/M | $3/M |
| >200K tokens | $1.00/M | $6/M |

## Common Issues

### Clock Skew Error
```
Invalid JWT: Token must be a short-lived token (60 minutes)
```
**Solution:** Ensure `apply_clock_skew_patch()` is called BEFORE importing Firebase.

### Auth Provider Not Found
```
No auth provider found for the given identifier
```
**Solution:** Use explicit credentials with `credentials.Certificate()`.

### Empty User List
If `firebase_user_analytics.py` shows only test users, you're likely missing real production users because:
1. The script was limiting to first 10 users
2. Real users have Firebase Auth UIDs, not test IDs like `test-user-123`

**Solution:** Use `campaign_manager.py analytics` with a known email address.

## Related Scripts
- `scripts/campaign_manager.py` - Main production query tool
- `scripts/firebase_user_analytics.py` - User behavior analytics
- `scripts/CLAUDE.md` - Script documentation
