---
description: Always check ~/.bashrc for credentials, API keys, passwords, and configuration values before asking user
type: usage
scope: project
---

# Bashrc Credential Guard

## Purpose
Guide Claude to always check `~/.bashrc` for any credentials, API keys, passwords, GCP projects, and configuration values BEFORE asking the user or looking elsewhere.

## Trigger phrases
- Questions about API credentials, passwords, or secrets
- Requests for deployment environment setup or configuration
- Missing environment variables or credentials
- GCP project configuration
- Email credentials or SMTP settings
- Any credential or configuration lookup

## Mandatory Protocol

🔑 **ALWAYS CHECK ~/.bashrc FIRST**: ⚠️ MANDATORY - BEFORE asking user or looking elsewhere
- Read `~/.bashrc` using the Read tool to find exported values
- Common patterns to search for:
  - `export API_KEY="..."`
  - `export EMAIL_USER="..."`
  - `export EMAIL_PASS="..."`
  - `export PASSWORD="..."`
  - `export GCP_PROJECT="..."`
  - `export GEMINI_API_KEY="..."`
  - `export GITHUB_TOKEN="..."`
  - Any `export VAR_NAME="value"` pattern

## Configuration Sources (Priority Order)
1. **~/.bashrc** - PRIMARY SOURCE (check FIRST, ALWAYS)
2. `.env` files - Secondary for local development
3. Platform secret managers - GitHub Secrets, GCP Secret Manager
4. User input - LAST RESORT (only if not found in bashrc)

## Common Use Cases

### 1. API Keys and Credentials
```bash
# Read ~/.bashrc to find:
export GEMINI_API_KEY="AIzaSy..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GITHUB_TOKEN="ghp_..."
```

### 2. Email Configuration
```bash
# Read ~/.bashrc to find:
export EMAIL_USER="user@gmail.com"
export EMAIL_PASS="app-password-here"
```

### 3. GCP Project Configuration
```bash
# Read ~/.bashrc to find:
export GCP_PROJECT="worldai"
export GCP_REGION="us-central1"
```

### 4. Database and Service URLs
```bash
# Read ~/.bashrc to find:
export DATABASE_URL="postgresql://..."
export REDIS_URL="redis://..."
```

## Security Best Practices

### Never Commit Secrets
- Never commit real keys to git repositories
- Store them in `~/.bashrc` (gitignored by default)
- Reference `.env.example` for required variables without actual values

### Use Bashrc Values for CI/CD
- When setting GitHub Secrets, use values from `~/.bashrc`
- When configuring GCP Secret Manager, source from `~/.bashrc`
- When updating environment variables, check `~/.bashrc` first

### Offer Redacted Examples
- When showing credential examples, redact sensitive parts
- Example: `export API_KEY="AIzaSy...XXX"` (showing only prefix)

## Troubleshooting Flow

1. **Missing Credential Error**
   - FIRST: Read `~/.bashrc` to check if credential exists
   - Check pattern: `grep CREDENTIAL_NAME ~/.bashrc`
   - If found: Use the value from bashrc
   - If not found: Ask user to add it to bashrc

2. **Configuration Mismatch**
   - FIRST: Read `~/.bashrc` for the canonical value
   - Compare with current configuration
   - Update configuration to match bashrc value

3. **Deployment Failures**
   - FIRST: Read `~/.bashrc` to verify all required credentials
   - Check if CI/CD secrets match bashrc values
   - Update secrets if they differ from bashrc

## Response Structure

1. Acknowledge the need for credentials/configuration
2. Read `~/.bashrc` FIRST to check for existing values
3. If found: Use the values from bashrc
4. If not found: Guide user to add them to bashrc
5. Provide commands to verify the values are set correctly

## Integration with Other Systems

### GitHub Secrets
- Source all secret values from `~/.bashrc`
- Use `gh secret set` commands with bashrc values
- Example: `gh secret set EMAIL_USER --body "$EMAIL_USER"`

### GCP Configuration
- Read GCP project from `~/.bashrc` first
- Use bashrc values for deployment configuration
- Ensure `.github/workflows/*.yml` matches bashrc values

### Local Development
- `.env` files should mirror bashrc values
- Use bashrc as the single source of truth
- Sync .env files with bashrc when values change

## Common Patterns in Bashrc

```bash
# API Keys
export GEMINI_API_KEY="AIzaSy..."
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."

# Email/SMTP
export EMAIL_USER="user@gmail.com"
export EMAIL_PASS="app-password"

# Cloud Platforms
export GCP_PROJECT="worldai"
export AWS_REGION="us-east-1"

# GitHub
export GITHUB_TOKEN="ghp_..."
export GITHUB_USER="username"

# Database
export DATABASE_URL="postgresql://..."
export REDIS_URL="redis://..."
```

## Remember

- **~/.bashrc is the FIRST place to check** - Not the last resort
- **Always read before asking** - Don't ask user for values that are in bashrc
- **Verify values exist** - Use `grep` or Read tool to confirm
- **Use bashrc for CI/CD** - All secrets should come from bashrc
- **Single source of truth** - Bashrc is the canonical source for credentials
