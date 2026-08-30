---
description: Send a message to Hermes via the local gateway (localhost:8643) and show the response
---

# /hermes

Send a message to the Hermes agent through the local gateway and display the response.

**Usage**: `/hermes <message>`

**Flow**: Claude Code → POST http://localhost:8643/v1/chat/completions → Hermes agent → response

## Action

Execute the following immediately with the Bash tool:

```bash
MSG='$ARGUMENTS'

# Sync call — wait for Hermes to respond (max 90s)
RESPONSE=$(curl -s -X POST http://localhost:8643/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"hermes-agent\",\"messages\":[{\"role\":\"user\",\"content\":\"$MSG\"}]}" \
  --max-time 90 2>&1)

EXIT=$?
if [ $EXIT -ne 0 ]; then
  echo "Gateway error (exit $EXIT). Is the gateway running? Check: curl http://localhost:8643/health"
  exit 1
fi

# Extract and print the reply
echo "$RESPONSE" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if 'choices' in d:
        print(d['choices'][0]['message']['content'])
    elif 'error' in d:
        print('Hermes error:', d['error'].get('message', d['error']))
    else:
        print('Unexpected response:', json.dumps(d, indent=2))
except Exception as e:
    print('Parse error:', e)
    print(sys.stdin.read())
"
```

Show the Hermes response to the user.

## Async variant (fire-and-forget)

For non-interactive alerting (e.g. from scripts), use the async endpoint:

```bash
curl -s -X POST http://localhost:8643/v1/runs \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"hermes-agent\",\"input\":\"$MSG\"}" \
  --max-time 5
```

This returns immediately with `{"run_id":"...","status":"started"}` — Hermes processes in background and will DM the user on Slack.
