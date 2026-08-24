---
name: spicy_remove
description: Remove egregious content from campaign story history and game state when model safety blocks cause empty responses or zero candidates
---

# Spicy Remove Skill

Use this skill when a campaign's interaction streams fail with empty responses or zero candidates due to model safety blocks triggering on egregious content in the story history or game state.

## Principle: Egregious vs General Spicy Content
This workflow is designed to **only remove egregious safety-violating content** that blocks model generation, while leaving **general consensual sex or spicy scenes intact**:

* **Egregious/Violating content to remove**:
  * Non-consensual sexual acts, sexual assault, forced submission, or torture.
  * Incestuous themes or terminology.
  * Explicit/vulgar slang words (e.g., `cumswap`, `cum-swapping`, `cum-streaked`, `blowjob`, `gangbang`, `deflower`, `prostitute`).
* **General spicy content to keep**:
  * Consensual romance, intimacy, passion, and generic spicy descriptions that do not involve non-consensual themes, violence, or explicit vulgar slang words.

---

## Action: Clean Campaign In-Place in Firestore

Execute the utility script `scripts/spicy_remove.py` to recursively scan and sanitize the campaign's `current_state` and `story` documents.

### Usage
```bash
# Run a dry-run to preview changes first
./vpython scripts/spicy_remove.py <campaign_id> --dry-run

# Apply the sanitization in-place in Firestore
./vpython scripts/spicy_remove.py <campaign_id>
```

### What the Script Does:
1. Automatically locates the campaign and its owner user UID across all users in Firestore.
2. Recursively traverses all nested dictionary and list values in `game_states/current_state` (including character histories, log entries, and `social_hp_challenge` fields).
3. Recursively scans all documents in the `story` subcollection.
4. Identifies egregious keywords and cleanses slang words like `cum` (safely ignoring common words like `document` or `cumulative`).
5. Replaces unsafe string values with safe, clinical descriptions:
   * **Short fields/statuses**: replaced with clean summaries (e.g., `"Under guard, cooperating with the Shogunate."`).
   * **Narrative blocks**: replaced with a safe story progression block describing the capture and confinement of captives under guard.
6. Saves the updated fields back to Firestore.
