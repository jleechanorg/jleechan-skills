---
description: Get multi-model second opinion on design, code review, or bugs
aliases: [secondopinion]
type: ai
execution_mode: immediate
---

# Second Opinion Command

Get comprehensive multi-model AI feedback on your code, design decisions, or bug analysis.

**🚀 Uses command-line approach to bypass 25K token limits and send full PR context!**

---

## ⚠️ CRITICAL: AI Universe Server Routing (MANDATORY)

**This command MUST route ALL requests through the AI Universe MCP server.**

### The Only Valid Endpoint
Set an environment variable so the endpoint can switch between dev/stage/prod without editing docs:
```
export AI_UNIVERSE_MCP_ENDPOINT="${AI_UNIVERSE_MCP_ENDPOINT:-https://ai-universe-backend-dev-114133832173.us-central1.run.app/mcp}"
```
> Use the dev URL only as the default. Override `AI_UNIVERSE_MCP_ENDPOINT` for staging/production deployments.

### BANNED Anti-Patterns (NEVER DO THESE)

❌ **NEVER** call Gemini MCP tools directly (e.g., `mcp__gemini__*`, `mcp__google__*`)
❌ **NEVER** call Perplexity MCP tools directly (e.g., `mcp__perplexity__*`)
❌ **NEVER** call OpenAI MCP tools directly (e.g., `mcp__openai__*`)
❌ **NEVER** use WebSearch as a substitute for second opinion
❌ **NEVER** skip the AI Universe authentication flow
❌ **NEVER** construct direct API calls to Gemini/Perplexity/OpenAI endpoints

### WHY This Matters

The AI Universe server provides:
1. **Unified Authentication** - One OAuth flow for all models
2. **Cost Tracking** - Centralized billing and usage metrics
3. **multi-model orchestration** - Parallel calls to Gemini, Perplexity, OpenAI
4. **Synthesis Engine** - Combines responses into unified verdict
5. **Source Aggregation** - 50+ authoritative sources per analysis
6. **Rate Limiting** - Fair usage across all authenticated users

**If you call model MCPs directly, you bypass all these benefits and get inferior results.**

---

## Usage

```bash
# Get second opinion on current PR branch
/secondo

# Specify feedback type
/secondo design
/secondo code-review
/secondo bugs

# With specific question
/secondo "Should I use Redis or in-memory caching for rate limiting?"
```

## How It Works

This command uses a direct approach with auth-cli.mjs for secure token management:

1. **Authentication** (Auto-Refresh):
   - Uses `~/.claude/scripts/auth-cli.mjs token` for secure token retrieval
   - Automatically refreshes expired ID tokens using refresh token (silent, no browser popup)
   - ID tokens expire after 1 hour, refresh tokens enable 30+ day sessions
   - Only opens browser for initial login or if refresh token expires

2. **Gather Full PR Context** *(automated via `build_second_opinion_request.py`)*:
   - Resolve branch + base reference (prefers `SECOND_OPINION_BASE_REF`, falls back to `origin/main` → `main` → `master`)
   - Capture `git status --short`, `git diff --stat`, and recent commits for orientation
   - Generate a full diff versus the base ref (truncated to stay under token budgets with explicit notices)
   - Attach per-file patches (up to configurable limit) so the MCP tool sees real code snippets instead of summaries

3. **Build Comprehensive Request**:
   - Create detailed analysis request (optimized to stay under 25K tokens)
   - Include all relevant code context
   - Add production context and testing requirements

4. **Direct MCP Server Call**:
   - Uses HTTPie with auto-refreshed Bearer token
   - Sends to the endpoint specified by `AI_UNIVERSE_MCP_ENDPOINT` (dev URL is the default)
   - Handles streaming responses properly
   - Saves results locally

5. **Multi-Model Analysis**:
   - Gemini (Primary model)
   - Perplexity (Secondary)
   - OpenAI (Secondary)
   - Synthesis with 50+ authoritative sources

6. **Results Display**:
   - Save comprehensive report to `tmp/secondo_analysis_[timestamp].md`
   - Display verdict and key findings
   - Show token usage and cost breakdown

## Implementation Protocol

When executing `/second_opinion` or `/secondo`:

> **Testing note (documentation-only update):** This change clarifies routing and auth requirements for the existing workflow. No application code was modified, so no automated test suite was rerun for this documentation revision.

### Execution Strategy

**PRIMARY APPROACH: Use MCP CLI (Recommended)**

Try the installed MCP server first using Claude Code's built-in MCP CLI:

```bash
# Check if second-opinion-tool MCP server is available
if mcp-cli tools second-opinion-tool 2>&1 | grep -q "agent.second_opinion"; then
  echo "✅ Using MCP CLI approach"
  USE_MCP_CLI=true
else
  echo "⚠️ MCP server not available, falling back to manual CLI"
  USE_MCP_CLI=false
fi
```

**FALLBACK APPROACH: Manual CLI with HTTPie**

If MCP CLI is not available or fails, use the manual HTTP approach with authentication.

---

### Phase 0: Memory Search Context (parallel subagent)

**Action Steps:**
1. **Run full memory search** in background using `/e` to gather context from ALL memory sources:
   ```
   /e /memory_search "$ARGUMENTS"
   ```
2. Display results as "📍 Prior Context Found" — these should inform the second opinion to avoid re-analyzing known issues
3. Continue to authentication while memory search runs in parallel

### Step 0: Authentication Setup (Auto-Refresh)

**Note**: Only required for FALLBACK approach. MCP CLI handles auth automatically.
```bash
# Verify auth-cli.mjs is installed
if [ ! -f "$HOME/.claude/scripts/auth-cli.mjs" ]; then
  echo "❌ auth-cli.mjs not found. Run /localexportcommands to install"
  exit 1
fi

# CRITICAL: Use AI Universe Firebase credentials with VITE_ prefix (required by auth-cli.mjs)
export VITE_AI_UNIVERSE_FIREBASE_PROJECT_ID="${VITE_AI_UNIVERSE_FIREBASE_PROJECT_ID:-ai-universe-b3551}"
export VITE_AI_UNIVERSE_FIREBASE_AUTH_DOMAIN="${VITE_AI_UNIVERSE_FIREBASE_AUTH_DOMAIN:-ai-universe-b3551.firebaseapp.com}"
# API key - hardcoded default for AI Universe shared service (safe to expose per Firebase security model)
export VITE_AI_UNIVERSE_FIREBASE_API_KEY="${VITE_AI_UNIVERSE_FIREBASE_API_KEY:-[REDACTED_GCP_KEY]}"

# Get token (auto-refreshes if expired using refresh token)
# This is silent - only prompts for login if refresh token is invalid/missing
TOKEN=$(node ~/.claude/scripts/auth-cli.mjs token)

# If this fails, user needs to authenticate with AI Universe credentials
if [ $? -ne 0 ]; then
  echo "❌ Authentication failed. Please run:"
  echo "   VITE_AI_UNIVERSE_FIREBASE_PROJECT_ID=ai-universe-b3551 \\"
  echo "   VITE_AI_UNIVERSE_FIREBASE_AUTH_DOMAIN=ai-universe-b3551.firebaseapp.com \\"
  echo "   VITE_AI_UNIVERSE_FIREBASE_API_KEY=[REDACTED_GCP_KEY] \\"
  echo "   node ~/.claude/scripts/auth-cli.mjs login"
  exit 1
fi
```

**Key Behavior**:
- **AI Universe Credentials Required**: Uses `ai-universe-b3551` Firebase project (NOT worldarchitecture-ai)
- **Seamless Auto-Refresh**: Automatically renews ID tokens using refresh token (no browser popup)
- **30+ Day Sessions**: Refresh tokens enable long-lived sessions without re-authentication
- **Browser Only When Needed**: Only opens browser for initial login or if refresh token expires
- **Same Token File**: Uses `~/.ai-universe/auth-token.json` (exact same as AI Universe repo)

### Step 1: Gather PR Context *(now automated)*

`skills/second_opinion_workflow/scripts/request_second_opinion.sh` calls
`build_second_opinion_request.py` to harvest the full PR delta. The helper:

- Resolves the comparison base (env override `SECOND_OPINION_BASE_REF`, then `origin/main` → `main` → `master`, finally `HEAD^`).
- Captures branch name, repo root, remote URL, `git status --short`, `git diff --stat`, recent commits, and the full diff.
- Extracts per-file patches for up to `SECOND_OPINION_MAX_FILES` (default 20) with truncation markers when limits are hit.
- Annotates the payload with `gitContextNotices` so the MCP tool sees exactly what was trimmed.

Manual usage if you want to inspect the payload directly:

```bash
python3 skills/second_opinion_workflow/scripts/build_second_opinion_request.py \
  /tmp/secondo_request.json \
  "What should I double-check before merging?" \
  3 \
  origin/main
```

Tune the capture limits with environment variables:

```bash
export SECOND_OPINION_BASE_REF=origin/main   # override comparison base
export SECOND_OPINION_MAX_FILES=25           # number of per-file patches to attach
export SECOND_OPINION_MAX_DIFF_CHARS=32000   # full diff char budget
export SECOND_OPINION_MAX_PATCH_CHARS=8000   # per-file diff char budget
```

### Step 2: Build Analysis Request

The generated payload now includes the git context automatically:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "agent.second_opinion",
    "arguments": {
      "question": "Should I land this patch set as-is?",
      "maxOpinions": 3,
      "gitContext": {
        "branch": "feature/refactor",
        "base": "origin/main",
        "diffstat": "…",
        "recentCommits": "…",
        "changedFiles": [
          {"status": "M", "path": "$PROJECT_ROOT/api/routes.py"},
          {"status": "A", "path": "$PROJECT_ROOT/services/cache.py"}
        ],
        "patches": {
          "$PROJECT_ROOT/api/routes.py": "@@ -42,6 +42,15 @@ …",
          "$PROJECT_ROOT/services/cache.py": "@@ -0,0 +1,200 @@ …"
        },
        "limits": {
          "maxFiles": 20,
          "diffCharLimit": 24000,
          "patchCharLimit": 6000
        }
      },
      "gitContextNotices": [
        "git diff origin/main...HEAD truncated by 1520 characters (limit 24000)."
      ]
    }
  },
  "id": 1
}
```

> 💡 You can still tailor the natural-language question, but you no longer need to paste diff snippets manually—the helper attaches them for you.

### Step 3: Execute Request

**Option A: MCP CLI Approach (Primary)**

```bash
# First, check the MCP CLI tool schema
mcp-cli info second-opinion-tool/agent.second_opinion

# Prepare the request payload (simplified for MCP CLI)
QUESTION="${1:-Should I land this patch set as-is?}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Call via MCP CLI
mcp-cli call second-opinion-tool/agent.second_opinion - <<EOF
{
  "question": "$QUESTION",
  "maxOpinions": 3,
  "gitContext": $(cat /tmp/secondo_git_context.json)
}
EOF > /tmp/secondo_analysis_${TIMESTAMP}.json

# Check if successful
if [ $? -eq 0 ] && [ -s /tmp/secondo_analysis_${TIMESTAMP}.json ]; then
  echo "✅ Analysis complete via MCP CLI"
  echo "📄 Results: /tmp/secondo_analysis_${TIMESTAMP}.json"
else
  echo "⚠️ MCP CLI failed, falling back to manual approach"
  USE_MCP_CLI=false
fi
```

**Option B: Manual HTTPie Approach (Fallback)**

```bash
# Call MCP server with HTTPie (matches request_second_opinion.sh)
MCP_ENDPOINT="${AI_UNIVERSE_MCP_ENDPOINT:-https://ai-universe-backend-dev-114133832173.us-central1.run.app/mcp}"
http POST "$MCP_ENDPOINT" \
  "Accept:application/json, text/event-stream" \
  "Authorization:Bearer $TOKEN" \
  < /tmp/secondo_request.json \
  --timeout=180 \
  --print=b > /tmp/secondo_response.json

# Check if successful
if [ $? -eq 0 ] && [ -s /tmp/secondo_response.json ]; then
  echo "✅ Analysis complete"
else
  echo "❌ Request failed"
  exit 1
fi
```

### Step 4: Parse and Display Results

Extract from `/tmp/secondo_response.json`:
1. Parse the JSON response (look for `result.content[0].text`)
2. Extract verdict, token counts, costs, sources
3. Save formatted report to `tmp/secondo_analysis_[timestamp].md`
4. Display key findings to user

**Example parsing**:
```bash
# Extract the main response text
jq -r '.result.content[0].text' /tmp/secondo_response.json > /tmp/secondo_parsed.txt

# Extract metrics if available
TOKENS=$(jq -r '.result.content[0].text' /tmp/secondo_response.json | grep -o 'Total Tokens: [0-9,]*' | head -1)
COST=$(jq -r '.result.content[0].text' /tmp/secondo_response.json | grep -o 'Total Cost: \$[0-9.]*' | head -1)
```

## Token Optimization

**Maximum token budget**: 24,900 tokens (stay under 25K limit)

**Allocation strategy**:
- **Request overhead**: ~100 tokens (JSON structure)
- **Question/context**: ~500-1000 words (optimize for clarity)
- **Git diff stats**: Full output (~100-500 tokens)
- **Critical code sections**: ~15K tokens (selective, not full files)
- **Commit messages**: ~200 tokens
- **Metadata**: ~100 tokens

**Tips to maximize context**:
1. Include git diff --stat (compact, informative)
2. Select critical changed sections (not full files)
3. Prioritize files with complex logic changes
4. Keep question focused (~500 words)
5. Skip unchanged context

## Authentication & Rate Limits

**Authentication**: Required via Firebase OAuth (exact same as AI Universe repo)
- **Initial Login**: `node ~/.claude/scripts/auth-cli.mjs login` (browser-based OAuth, run outside Claude Code)
- **Check Status**: `node ~/.claude/scripts/auth-cli.mjs status` (view current auth status)
- **Token Location**: `~/.ai-universe/auth-token.json` (ID token + refresh token)
- **Session Duration**: 30+ days (refresh tokens auto-renew ID tokens silently)
- **Auto-Refresh**: `/secondo` automatically refreshes expired ID tokens (no browser popup needed)

**Token Lifecycle**:
- **ID Token**: Expires after 1 hour (Firebase security policy)
- **Refresh Token**: Enables automatic ID token renewal for 30+ days
- **Auto-Renewal**: Silent, seamless - only opens browser if refresh token expires

**When You'll Need to Re-authenticate**:
- Initial setup (no token file exists)
- After 30+ days (when refresh token expires)
- If token file is corrupted or manually deleted

**Rate Limits**: Applied per authenticated user based on Firebase account

**Practical limits**:
- Server timeout: 180 seconds max
- Token limit: 25,000 tokens per response
- Cost: ~$0.10 per full PR analysis (3 models)

## Output Format

Display results in markdown with:
- 📊 **Summary**: Models used, tokens, cost, sources
- 🎯 **Verdict**: Unanimous consensus or majority opinion
- ⚠️ **Critical Issues**: Security, correctness, production safety
- 💡 **Model Perspectives**: Individual model insights
- ✅ **Validation**: What was confirmed as correct
- 🔗 **Sources**: Authoritative references (50+)

**Save to**: `tmp/secondo_analysis_[timestamp].md`

## Success Criteria

✅ Request completes successfully (curl exit code 0)
✅ Response file is non-empty
✅ Response contains valid JSON with `result.content`
✅ Analysis report saved to tmp directory
✅ User sees verdict and key findings

## Error Handling

**Common issues**:
1. **Token limit exceeded**: Reduce code context, keep question focused
2. **Timeout**: Complex analysis may take 60-120 seconds, use `--max-time 180`
3. **Empty response**: Check curl exit code, verify network connectivity
4. **JSON parse error**: Response may be streaming format, extract text content first

## Example Execution Flow

```
User: /secondo

1. Gather PR context:
   ✓ Branch: fix_mcp
   ✓ Changed files: 18 files (+2448/-799)
   ✓ Git diff saved to /tmp/secondo_diff_full.txt
   ✓ Commits: 5 commits analyzed

2. Build analysis request:
   ✓ Question: 487 words
   ✓ Code context: 14,250 tokens
   ✓ Total estimated: 23,890 tokens (95.6% of limit)

3. Execute request:
   ✓ curl -X POST [MCP endpoint]
   ✓ Response: 73KB received in 47 seconds
   ✓ Status: HTTP 200 OK

4. Parse results:
   ✓ Models: 3 (Gemini, Perplexity, OpenAI)
   ✓ Total tokens: 24,964
   ✓ Total cost: $0.10193
   ✓ Sources: 52 authoritative references

5. Display verdict:
   🎯 UNANIMOUS VERDICT: CORRECT (with caveats)

   ✅ Fix is safe for production
   ⚠️ Array initialization discipline required
   📊 Report saved: tmp/secondo_analysis_20251031_1847.md
```
