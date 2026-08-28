---
description: Complete workflow for using AI Universe MCP /secondo command
type: usage
scope: project
---

# AI Universe Second Opinion Workflow

**Quick start:** Use `/secondo` or the HTTPie helper script to gather multi-model analysis (Cerebras, Gemini, Perplexity, GPT-4o + synthesis).

---

## Activation cues
- Requests to run or debug the AI Universe "second opinion" workflow.
- Follow-ups after failed `/secondo` runs or HTTPie 401/5xx errors.
- Planning sessions that need step-by-step instructions for MCP calls.
- Questions about cost, rate limits, or interpreting multi-model output.

## Prerequisites & authentication
1. **Verify auth-cli.mjs installation**:
   ```bash
   test -f ~/.claude/scripts/auth-cli.mjs && echo "✅ Installed" || echo "❌ Not found - run /localexportcommands"
   ```
2. **Check authentication status**:
   ```bash
   node ~/.claude/scripts/auth-cli.mjs status
   ```
3. **If not authenticated or token expired**, run login (opens browser for OAuth):
   ```bash
   # Run this outside Claude Code in a regular terminal
   node ~/.claude/scripts/auth-cli.mjs login
   ```
4. Ensure `http` (HTTPie), `jq`, `python3`, and `node` (>=20.0.0) are installed in the environment.

> ℹ️ **Seamless Auto-Refresh**: The `/secondo` command uses the exact same auth-cli.mjs from AI Universe repo. If your token is valid, it does nothing. If expired, it auto-refreshes using your refresh token (silent, no browser popup). Only prompts for login if refresh token expires (30+ days).

> ℹ️ **Token Location**: All tokens stored in `~/.ai-universe/auth-token.json` (same as AI Universe repo)
> - ID token: 1-hour expiration
> - Refresh token: enables 30+ day sessions

> ℹ️ For a dedicated authentication walkthrough see [ai-universe-auth.md](ai-universe-auth.md). Dependency notes live in [secondo-dependencies.md](secondo-dependencies.md).

## Primary commands
| Scenario | Command |
| --- | --- |
| Quick question (when SlashCommand is working) | `/secondo "Should I use Redis or in-memory caching?"` |
| Build MCP request with PR context | `python3 skills/second_opinion_workflow/scripts/build_second_opinion_request.py /tmp/mcp_request.json "QUESTION" 3 origin/main` |
| Call MCP via HTTPie | `http POST https://ai-universe-backend-dev-114133832173.us-central1.run.app/mcp "Authorization:Bearer $TOKEN" < /tmp/mcp_request.json --timeout=180 --print=b` |
| Parse embedded JSON response | `jq -r '.result.content[0].text' /tmp/mcp_response.json > /tmp/mcp_parsed.json` |
| Summarize models/costs | `python3 skills/second_opinion_workflow/scripts/parse_second_opinion.py /tmp/mcp_parsed.json` |
| End-to-end helper | `skills/second_opinion_workflow/scripts/request_second_opinion.sh "QUESTION" [MAX_OPINIONS]` |

## Recommended workflow (HTTPie)
1. **Generate the request payload** (captures diff + per-file patches automatically):
   ```bash
   python3 skills/second_opinion_workflow/scripts/build_second_opinion_request.py \
     /tmp/mcp_request.json \
     "YOUR QUESTION HERE" \
     3 \
     origin/main
   ```
   Adjust `SECOND_OPINION_MAX_FILES`, `SECOND_OPINION_MAX_DIFF_CHARS`, or `SECOND_OPINION_MAX_PATCH_CHARS` if you need more/less context.
2. **(Optional) Inspect/tweak** `/tmp/mcp_request.json` to refine the natural-language question while keeping the attached git context intact.
3. **Get authentication token** (auto-refresh from AI Universe repo):
   ```bash
   # Get token (auto-refreshes if expired, does nothing if valid)
   TOKEN=$(node ~/.claude/scripts/auth-cli.mjs token)
   ```
4. **Send request** (allowing up to 180s for cold starts):
   ```bash
   http POST https://ai-universe-backend-dev-114133832173.us-central1.run.app/mcp \
     "Accept:application/json, text/event-stream" \
     "Authorization:Bearer $TOKEN" \
     < /tmp/mcp_request.json \
     --timeout=180 \
     --print=b > /tmp/mcp_response.json
   ```
5. **Parse embedded JSON** and display summary (or use the helper script):
   ```bash
   jq -r '.result.content[0].text' /tmp/mcp_response.json > /tmp/mcp_parsed.json
   python3 <<'PYEOF'
   import json
   with open('/tmp/mcp_parsed.json', 'r') as f:
       data = json.load(f)
   print(f"✅ Received responses from {data['summary']['totalModels']} models")
   print(f"💰 Total cost: ${data['summary']['totalCost']:.4f}")
   print(f"📊 Total tokens: {data['summary']['totalTokens']:,}")
   print("\nPrimary response:\n")
   print(data['primary']['response'])
   PYEOF
   ```
   Or run:
   ```bash
   python3 skills/second_opinion_workflow/scripts/parse_second_opinion.py /tmp/mcp_parsed.json
   ```
6. **Review synthesis** to confirm consensus and recommended actions.

> 📌 Need more HTTPie patterns? Use [ai-universe-httpie.md](ai-universe-httpie.md) as a companion reference.

## SlashCommand fallback (Option A)
Use `/secondo "QUESTION"` for quick prompts **only when the command file is healthy**. If it fails or hangs, switch to the HTTPie workflow.

## Automation helper script
Run the bundled script from repo root for a streamlined flow:
```bash
skills/second_opinion_workflow/scripts/request_second_opinion.sh "How should I harden our auth endpoints?" 4
```
The script:
1. Validates token presence and checks that `MAX_OPINIONS` is a positive integer.
2. Invokes `build_second_opinion_request.py` to embed branch/base metadata, diffstat, recent commits, and per-file patches into the payload.
3. Calls the MCP endpoint with HTTPie and a 180s timeout.
4. Parses the embedded JSON and prints model count, token usage, cost, and the primary + synthesis responses.
5. Writes raw artifacts to `/tmp`; set `KEEP_TEMP_FILES=1` when running the script to keep them after completion.

For advanced prompting templates and interactive options, see the existing `~/.claude/scripts/secondo-cli.sh` utility.

## Troubleshooting
- **502 Bad Gateway / cold start** → Retry after 30–60 seconds. Send a lightweight `"What is 2+2?"` request first to warm the backend.
- **401 Unauthorized / invalid token** → Token expired (30-day TTL). Re-run `node scripts/auth-cli.mjs login` outside Claude Code.
- **"command -c invalid" errors** → Avoid nested command substitutions. Use heredocs + two-step token capture as shown above.
- **Parsing failures** → Always extract `.result.content[0].text` before loading JSON. Use the helper Python snippet or script for safe parsing.

## Cost & rate limits
- Authenticated users: 100 requests/hour, with multi-model synthesis limited to 1/hr.
- Typical cost ranges: $0.01–$0.20 depending on prompt complexity.
- Model cost breakdown (approx.): Cerebras $0.003, Gemini 2.5 Flash $0.001, Perplexity $0.002, GPT-4o $0.10, synthesis $0.005.

## Reporting expectations
- Confirm authentication status and whether `/secondo` or HTTPie path was used.
- Provide model count, total tokens, and total cost from the parsed summary.
- Include primary + synthesis takeaways or recommended next actions.
- Note any errors encountered and remediation steps (e.g., re-authentication, retries).

## Related references
- `skills/second_opinion_workflow/scripts/` for helper tooling.
- [ai-universe-auth.md](ai-universe-auth.md) for login instructions.
- [secondo-dependencies.md](secondo-dependencies.md) for HTTPie/JQ requirements.
- [ai-universe-httpie.md](ai-universe-httpie.md) for advanced HTTPie patterns.
