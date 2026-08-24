---
description: Test API keys against jleechanorg/ai_universe repository services
type: testing
scope: project
---

# Test API Keys Against AI Universe Repository

This skill provides a script to test API keys from your `.bashrc` against the actual services used by the `jleechanorg/ai_universe` repository.

## Overview

The script:
- Clones the `ai_universe` repository to `/tmp`
- Tests API keys against the actual API endpoints used by the repo
- Validates GitHub access to the repository
- Tests LLM API keys (Gemini, OpenAI, Anthropic, Perplexity, OpenRouter)
- Provides a summary of test results

## Prerequisites

- `curl` installed (usually pre-installed on macOS/Linux)
- `git` installed
- API keys configured in `~/.bashrc`
- Internet connection

## Usage

### Basic Usage

```bash
# Run the test script
bash /tmp/test_ai_universe_api_keys.sh
```

The script will:
1. Load API keys from `~/.bashrc`
2. Clone the `ai_universe` repository to `/tmp/ai_universe_api_test_*/`
3. Test each API key against its respective service
4. Display results and cleanup temporary files

### What Gets Tested

The script tests the following API keys (loaded from `~/.bashrc`):

| API Key | Service | Purpose in AI Universe |
|---------|---------|----------------------|
| `GITHUB_TOKEN` | GitHub API | Repository access and authentication |
| `GEMINI_API_KEY` | Google Gemini | Primary AI model for game master |
| `OPENAI_API_KEY` | OpenAI | Multi-model synthesis |
| `ANTHROPIC_API_KEY` | Anthropic Claude | Multi-model synthesis |
| `PERPLEXITY_API_KEY` | Perplexity | Multi-model synthesis |
| `OPENROUTER_API_KEY` | OpenRouter | Multi-model synthesis |

### Expected Output

```
========================================
AI Universe API Key Testing
========================================

Loading API keys from ~/.bashrc...
Cloning ai_universe repository...
✅ Repository cloned successfully

Checking API key usage in repository...
✅ Found API key references in:
  - backend/server.py
  - frontend/src/services/ai.ts

Testing API keys...

Testing GitHub repo access...
✅ GitHub token valid - Can access repo: jleechanorg/ai_universe

Testing Gemini API...
✅ Gemini API key valid - Can list models

Testing OpenAI API...
✅ OpenAI API key valid

Testing Anthropic API...
✅ Anthropic API key valid

Testing Perplexity API...
✅ Perplexity API key valid

Testing OpenRouter API...
✅ OpenRouter API key valid

========================================
Test Summary
========================================
Passed: 6
Failed: 0
Total: 6

✅ All API keys are valid!
```

## Troubleshooting

### Script Not Found

If the script doesn't exist at `/tmp/test_ai_universe_api_keys.sh`, you can recreate it:

```bash
# The script is created automatically, but if needed, you can ask Claude to recreate it
# or copy it from the project documentation
```

### API Keys Not Found

If you see "❌ API_KEY not set" errors:

1. **Verify keys are in `.bashrc`:**
   ```bash
   grep -E "export (GITHUB_TOKEN|GEMINI_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|PERPLEXITY_API_KEY|OPENROUTER_API_KEY)=" ~/.bashrc
   ```

2. **Reload your shell:**
   ```bash
   source ~/.bashrc
   ```

3. **Check key format:**
   - Keys should be exported with `export KEY_NAME="value"`
   - No spaces around the `=` sign
   - Quotes are optional but recommended

### GitHub Access Denied

If GitHub token test fails:

1. **Check token permissions:**
   - Token needs `repo` scope for private repositories
   - Token needs `read:org` for organization repositories

2. **Verify token is valid:**
   ```bash
   curl -H "Authorization: Bearer $GITHUB_TOKEN" \
        https://api.github.com/user
   ```

3. **Regenerate token if needed:**
   - Go to https://github.com/settings/tokens
   - Create new token with appropriate scopes

### API Key Invalid Errors

If an API key test fails:

1. **Check the key value:**
   ```bash
   echo $GEMINI_API_KEY  # Replace with the failing key name
   ```

2. **Verify key hasn't expired:**
   - Some API keys have expiration dates
   - Check your account dashboard for the service

3. **Check quota/credits:**
   - Some services may show "valid" but have no credits
   - Check your account balance

### Repository Clone Fails

If the repository clone fails:

1. **Check network connectivity:**
   ```bash
   ping github.com
   ```

2. **Verify repository exists:**
   ```bash
   curl -I https://github.com/jleechanorg/ai_universe
   ```

3. **Check GitHub access:**
   - Repository might be private
   - Your GitHub token needs appropriate permissions

## Integration with Other Tools

### Use with CI/CD

You can integrate this script into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Test API Keys
  run: |
    bash /tmp/test_ai_universe_api_keys.sh
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
    # ... other keys
```

### Use with Monitoring

Set up a cron job to test keys periodically:

```bash
# Add to crontab (crontab -e)
# Test API keys daily at 2 AM
0 2 * * * bash /tmp/test_ai_universe_api_keys.sh >> /tmp/api_key_test.log 2>&1
```

## Security Notes

- **Temporary Files**: The script creates temporary directories in `/tmp/` that are automatically cleaned up
- **API Keys**: Keys are loaded from `~/.bashrc` but not logged or stored
- **Repository**: Only clones the repository temporarily for analysis
- **Network**: Makes API calls to validate keys - ensure you're on a secure network

## Related Skills

- [ai-universe-auth.md](ai-universe-auth.md) - Authentication setup for AI Universe MCP server
- [ai-universe-httpie.md](ai-universe-httpie.md) - Using HTTPie with AI Universe APIs
- [gcp-deployment.md](gcp-deployment.md) - GCP deployment and service management

## Script Location

The script is located at:
- **Path**: `/tmp/test_ai_universe_api_keys.sh`
- **Working Directory**: `/tmp/ai_universe_api_test_*/` (temporary, auto-cleaned)
- **Repository Clone**: `/tmp/ai_universe_api_test_*/ai_universe/` (temporary)

## Maintenance

The script is automatically maintained and can be recreated if needed. To update:

1. Ask Claude to recreate the script
2. Or modify the script directly at `/tmp/test_ai_universe_api_keys.sh`

## Example Workflow

```bash
# 1. Test all API keys
bash /tmp/test_ai_universe_api_keys.sh

# 2. If GitHub fails, check token
curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user

# 3. If Gemini fails, test directly
curl "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY"

# 4. Fix any issues and re-run
bash /tmp/test_ai_universe_api_keys.sh
```
