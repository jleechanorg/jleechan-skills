---
name: gateway-upgrade
description: Safe gateway upgrade/downgrade with pre-flight checks, rollback, and post-verification
---

# Gateway Upgrade Safety Checklist

**MANDATORY before any `npm install -g openclaw@*`, `openclaw doctor --fix`, or gateway version change.**

## Pre-flight (run BEFORE upgrade)

```bash
# 1. Snapshot current state
CURRENT_VERSION=$(openclaw --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
CURRENT_PID=$(pgrep -f 'openclaw-gateway' | head -1)
echo "Current: v$CURRENT_VERSION PID=$CURRENT_PID"

# 2. Check for competing plists (MUST be exactly 1)
PLIST_COUNT=$(ls ~/Library/LaunchAgents/*openclaw*gateway* 2>/dev/null | wc -l | tr -d ' ')
echo "Gateway plists: $PLIST_COUNT"
ls ~/Library/LaunchAgents/*openclaw*gateway* 2>/dev/null
if [ "$PLIST_COUNT" -gt 1 ]; then
  echo "ABORT: Multiple gateway plists detected. Remove extras before upgrading."
  exit 1
fi

# 3. Backup config
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.pre-upgrade-$(date +%s)

# 4. Record active plist label
ACTIVE_LABEL=$(launchctl list 2>/dev/null | grep -E 'openclaw.*gateway' | awk '{print $3}' | head -1)
echo "Active launchd label: $ACTIVE_LABEL"

# 5. Verify Slack is working (baseline)
openclaw channels status --probe 2>&1 | grep -i slack
```

## Upgrade

```bash
# Install new version
/opt/homebrew/bin/npm install -g openclaw@<version>
openclaw --version  # verify

# CRITICAL: Check if doctor --fix is needed
# If it prompts for --fix, do NOT run it blindly.
# Instead, check what it wants to change:
openclaw doctor 2>&1 | head -40
# Only run --fix if you understand every change it will make.
```

## Post-flight (run AFTER upgrade)

```bash
# 1. Verify still exactly 1 plist
PLIST_COUNT=$(ls ~/Library/LaunchAgents/*openclaw*gateway* 2>/dev/null | wc -l | tr -d ' ')
if [ "$PLIST_COUNT" -gt 1 ]; then
  echo "ALERT: doctor --fix created a second plist. Remove the old one:"
  ls -la ~/Library/LaunchAgents/*openclaw*gateway*
  # Keep only the one matching the active label
fi

# 2. Verify config wasn't corrupted
python3 -c "import json; json.load(open('$HOME/.openclaw/openclaw.json')); print('Config JSON: valid')"

# 3. Verify critical config keys survived (doctor --fix can silently drop keys)
python3 -c "
import json
with open('$HOME/.openclaw/openclaw.json') as f:
    d = json.load(f)
checks = [
    ('agents.defaults.heartbeat', d.get('agents',{}).get('defaults',{}).get('heartbeat')),
    ('gateway.auth.token', d.get('gateway',{}).get('auth',{}).get('token')),
    ('channels.slack.appToken', d.get('channels',{}).get('slack',{}).get('appToken')),
    ('channels.slack.botToken', d.get('channels',{}).get('slack',{}).get('botToken')),
]
for path, val in checks:
    status = 'OK' if val else 'MISSING'
    print(f'  {path}: {status}')
"

# 4. Rebuild native modules
bash ~/.openclaw/scripts/rebuild-native-modules.sh

# 5. Restart gateway
launchctl kickstart -k gui/$(id -u)/$ACTIVE_LABEL

# 6. Wait and verify
sleep 10
openclaw channels status --probe 2>&1 | grep -i slack
tail -5 ~/.openclaw/logs/gateway.err.log | grep -v 'plugin\|tools.profile'
```

## Rollback

```bash
# If upgrade fails, rollback immediately:
/opt/homebrew/bin/npm install -g openclaw@$CURRENT_VERSION
cp ~/.openclaw/openclaw.json.pre-upgrade-* ~/.openclaw/openclaw.json  # restore config
python3 -c "
import json
with open('$HOME/.openclaw/openclaw.json') as f:
    d = json.load(f)
d['meta']['lastTouchedVersion'] = '$CURRENT_VERSION'
with open('$HOME/.openclaw/openclaw.json', 'w') as f:
    json.dump(d, f, indent=2)
"
launchctl kickstart -k gui/$(id -u)/$ACTIVE_LABEL
```

## Red flags that mean STOP

- `doctor --fix` wants to create a new plist → check for existing plists first
- Config says "last written by newer version" → update `meta.lastTouchedVersion`
- Multiple `openclaw-gateway` processes → kill extras, verify single plist
- ThrottleInterval < 10 in plist → change to 30 (prevents restart storms)
- Slack `invalid_auth` after upgrade → token may be burned; check api.slack.com
