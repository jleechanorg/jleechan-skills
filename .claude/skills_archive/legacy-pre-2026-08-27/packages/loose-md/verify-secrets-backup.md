# /verify-secrets-backup — Check gitignored secret files are in Dropbox backup

Verify that all gitignored config files containing real tokens/secrets from `~/.openclaw/`
are present in the Dropbox backup at `~/Library/CloudStorage/Dropbox/openclaw_backup/latest/`.

## Required files to verify

Check each of these exists in the Dropbox backup AND is non-zero size AND was modified
within the last 7 days:

| File | Why it matters |
|------|---------------|
| `openclaw.json` | All API keys, Slack tokens, gateway tokens, OpenAI/MiniMax/XAI keys |
| `agents/main/agent/auth-profiles.json` | OAuth tokens for the main agent |
| `credentials/` | Provider credentials directory |
| `discord-eng-bot/openclaw.json` | Discord bot config (uses resolved tokens at runtime) |

## Steps

1. Run `~/.openclaw/scripts/dropbox-openclaw-backup.sh` to force a fresh backup
2. Check each required file exists in `~/Library/CloudStorage/Dropbox/openclaw_backup/latest/`
3. Check modification time is recent (within 24h ideally)
4. Report: ✓/✗ per file, age of backup, any missing files
5. If anything is missing or stale: re-run backup and report again

## Example check command

```bash
BACKUP=~/Library/CloudStorage/Dropbox/openclaw_backup/latest
for f in openclaw.json agents/main/agent/auth-profiles.json credentials; do
  if [ -e "$BACKUP/$f" ]; then
    age=$(( ($(date +%s) - $(stat -f %m "$BACKUP/$f")) / 3600 ))
    echo "✓ $f (${age}h ago)"
  else
    echo "✗ MISSING: $f"
  fi
done
```
