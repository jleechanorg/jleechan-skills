---
name: ai-universe-second-opinion-workflow
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
Before any authentication command, use the host's already loaded nvm setup to
resolve its installed Node 22. If nvm or Node 22 is unavailable, report that
prerequisite; do not use a different major version or change persistent defaults.

```bash
AUTH_NODE="$(nvm which 22)" || exit 1
[ -x "$AUTH_NODE" ] || exit 1
case "$("$AUTH_NODE" --version)" in v22.*) ;; *) exit 1 ;; esac
```

Use this same verified `AUTH_NODE` executable for every command below.

1. **Verify auth-cli.mjs installation**:
   ```bash
   test -f ~/.claude/scripts/auth-cli.mjs && echo "✅ Installed" || echo "❌ Not found - run /localexportcommands"
   ```
2. **Check authentication status**:
   ```bash
   "$AUTH_NODE" ~/.claude/scripts/auth-cli.mjs status
   ```
3. Follow `../ai-universe-auth/SKILL.md` for current authentication state and
   refresh handling. If the existing token is expired, call the existing
   `auth-cli.mjs token` command to refresh from the authorized credential store
   without printing the token. Retry the requested non-UI MCP call once after a
   successful refresh. Do not start a browser login from a 401 or stale token
   status. If refresh fails, use the canonical credential owner's Keychain
   presence probe (without displaying a value) and a cheap non-UI authenticated
   call. Only after both fail may you report the physical authentication
   dependency; do not ask for login from status output alone.
4. Ensure `http` (HTTPie), `jq`, and `python3` are installed.

> ℹ️ **Seamless Auto-Refresh**: The `/secondo` command uses the exact same auth-cli.mjs from AI Universe repo. If your token is valid, it does nothing. If expired, it auto-refreshes using your refresh token (silent, no browser popup). Only prompts for login if refresh token expires (30+ days).

> ℹ️ **Token Location**: All tokens stored in `~/.ai-universe/auth-token.json` (same as AI Universe repo)
> - ID token: 1-hour expiration
> - Refresh token: enables 30+ day sessions

> ℹ️ For a dedicated authentication walkthrough see [ai-universe-auth.md](../ai-universe-auth/SKILL.md). Dependency notes live in [secondo-dependencies.md](../secondo-dependencies/SKILL.md).

## Primary commands
| Scenario | Command |
| --- | --- |
| Quick question (when SlashCommand is working) | `/secondo "Should I use Redis or in-memory caching?"` |
| Build MCP request with PR context | `python3 skills/second_opinion_workflow/scripts/build_second_opinion_request.py "$REQUEST_FILE" "QUESTION" 3 origin/main` |
| Call MCP via HTTPie | `http POST https://ai-universe-backend-dev-114133832173.us-central1.run.app/mcp "Authorization:Bearer $TOKEN" < "$REQUEST_FILE" --timeout=180 --print=b` |
| Parse embedded JSON response | `jq -r '.result.content[0].text' "$RESPONSE_FILE" > "$PARSED_FILE"` |
| Summarize models/costs | `python3 skills/second_opinion_workflow/scripts/parse_second_opinion.py "$PARSED_FILE"` |
| End-to-end helper | `skills/second_opinion_workflow/scripts/request_second_opinion.sh "QUESTION" [MAX_OPINIONS]` |

## Recommended workflow (HTTPie)
1. **Generate the request payload** (captures diff + per-file patches automatically):
   ```bash
   RUN_DIR="$(mktemp -d /tmp/second-opinion.XXXXXX)"
   REQUEST_FILE="$RUN_DIR/mcp_request.json"
   RESPONSE_FILE="$RUN_DIR/mcp_response.json"
   PARSED_FILE="$RUN_DIR/mcp_parsed.json"
   python3 skills/second_opinion_workflow/scripts/build_second_opinion_request.py \
     "$REQUEST_FILE" \
     "YOUR QUESTION HERE" \
     3 \
     origin/main
   ```
   Adjust `SECOND_OPINION_MAX_FILES`, `SECOND_OPINION_MAX_DIFF_CHARS`, or `SECOND_OPINION_MAX_PATCH_CHARS` if you need more/less context.
2. **(Optional) Inspect/tweak** `"$REQUEST_FILE"` to refine the natural-language question while keeping the attached git context intact.
3. **Get authentication token** through the existing auth CLI (auto-refresh only from its designated credential store):
   ```bash
   # Get token (auto-refreshes if expired, does nothing if valid)
   TOKEN=$("$AUTH_NODE" ~/.claude/scripts/auth-cli.mjs token)
   ```
4. **Send request** (allowing up to 180s for cold starts):
   ```bash
   http POST https://ai-universe-backend-dev-114133832173.us-central1.run.app/mcp \
     "Accept:application/json, text/event-stream" \
     "Authorization:Bearer $TOKEN" \
     < "$REQUEST_FILE" \
     --timeout=180 \
     --print=b > "$RESPONSE_FILE"
   ```
5. **Parse embedded JSON** and display the summary with the parser tracked in
   the `worldarchitect.ai` repository. Run this workflow from that repository's
   root so the relative path resolves:
   ```bash
   jq -r '.result.content[0].text' "$RESPONSE_FILE" > "$PARSED_FILE"
   python3 skills/second_opinion_workflow/scripts/parse_second_opinion.py "$PARSED_FILE"
   ```
6. **Review synthesis** to confirm consensus and recommended actions.

> 📌 Need more HTTPie patterns? Use [ai-universe-httpie.md](../ai-universe-httpie/SKILL.md) as a companion reference.

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
- **401 Unauthorized / invalid token** → Follow the authentication recovery sequence above: inspect the response, refresh using the existing credential store, and perform the required credential-presence and non-UI probes. A 401 alone does not authorize or require interactive login.
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
- [ai-universe-auth.md](../ai-universe-auth/SKILL.md) for login instructions.
- [secondo-dependencies.md](../secondo-dependencies/SKILL.md) for HTTPie/JQ requirements.
- [ai-universe-httpie.md](../ai-universe-httpie/SKILL.md) for advanced HTTPie patterns.
