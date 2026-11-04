---
name: repro-copy
description: Copy a real campaign to <your-email@gmail.com>, replay a reported issue against a real local server + real LLM, and capture evidence that can survive review
---

# Repro Copy Workflow

Use this skill when you need to copy a real campaign to `<your-email@gmail.com>`,
replay a reported issue against a real local server + real LLM, and capture
evidence that can survive review.

## Twin baseline + test subject (no contamination)

If the user requires **two full copies** from production — **first copy never receives any turn** — and all replay on the **second** copy only (plus full `download_campaign` export to avoid drift), use **`.claude/skills/repro-twin-clone-evidence/SKILL.md`**. That is **not** the same as canonical+variant here (variant may delete the last scene).

## CRITICAL: Resolve Firebase UID first — always pass `--source-user-id`

Without `--source-user-id`, the script uses `_find_campaign_owner` to scan users
for the campaign, which is slow. If the owner cannot be resolved, you get a
**ValueError** with an explicit message. Pass `--source-user-id` whenever you
already know the owner UID to skip the scan.

```bash
# Step 0: resolve UID (required for any production campaign)
UID=$(./vpython -c "
import firebase_admin; from firebase_admin import auth, credentials; import os
cred = credentials.Certificate(os.path.expanduser('~/serviceAccountKey.json'))
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)
print(auth.get_user_by_email('<your-email@example.com>').uid)
")
if [ -z "$UID" ]; then
  echo "Failed to resolve Firebase UID" >&2
  exit 1
fi
# → <YOUR_UID>

./vpython scripts/repro_copy_campaign.py <campaign_id> \
  --source-user-id "$UID" \
  --issue "short issue description" \
  --start-local
```

## Optional flags

```bash
./vpython scripts/repro_copy_campaign.py <campaign_id> \
  --issue "missing planning block after level-up badge" \
  --user-input "I open my inventory and continue forward." \
  --server-url http://127.0.0.1:8081
```

Destructive variant mutation is opt-in:

```bash
./vpython scripts/repro_copy_campaign.py <campaign_id> \
  --issue "missing planning block after level-up badge" \
  --delete-last-scene \
  --force-delete-last-scene \
  --start-local
```

## What it does

1. Resolves the destination UID for `<your-email@gmail.com>`.
2. Creates two copies of the source campaign:
   - canonical copy
   - variant copy
3. Replays the same input through a real local MCP server on both copies.
4. Optionally deletes the latest story scene from the variant copy before replay.
5. Writes a full evidence bundle under `/tmp/worldarchitectai/<branch>/repro_copy_campaign/...`.

## Evidence requirements

These are mandatory for evidence-bearing repro work:

- Canonical evidence standards: `~/.claude/skills/evidence-standards/SKILL.md`
- Tmux video template: `~/.claude/skills/evidence-standards/tmux-video-evidence.md`
- UI video template: `~/.claude/skills/evidence-standards/ui-video-evidence.md`

The script writes:

- `artifacts/tmux_repro_evidence.sh`
- `artifacts/ui_video_guide.md`

Use those to record captioned tmux and browser videos tied to the same commit.

## When to require UI video

If the reported issue is visible in the browser, UI video is mandatory. Show:

1. Canonical campaign route.
2. Replay input.
3. Resulting state.
4. Variant campaign route.
5. Same replay input.
6. Resulting state.

## Notes

- The script is real-mode only. Do not use mock services.
- If replay input cannot be inferred from story entries, pass `--user-input`.
- `--delete-last-scene` is off by default and requires
  `--force-delete-last-scene` because it irreversibly deletes the newest
  Firestore story document from the variant copy.
- The variant copy is intentionally not a full rollback; when deletion is
  enabled it removes the latest story scene to test how sensitive the repro is
  to immediate story context.
