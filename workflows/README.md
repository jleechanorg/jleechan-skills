# GitHub Actions Workflows - EXAMPLES ONLY

⚠️ **IMPORTANT: These workflows are EXAMPLES and require integration into your codebase.**

## What This Directory Contains

This directory contains **GitHub Actions workflow examples** exported from a working Claude Code project. These serve as reference implementations and templates for common CI/CD patterns.

## ⚠️ Why These Cannot Be Used As-Is

These workflows contain project-specific configurations that **must be adapted** before use:

1. **GCP Project IDs**: References to `$GCP_PROJECT_ID` need your actual Google Cloud project
2. **Repository References**: `$GITHUB_REPOSITORY` placeholders need your `owner/repo`
3. **Service Accounts**: Workload Identity Federation and service account configurations are project-specific
4. **Secrets**: Workflow secrets (API keys, tokens) must be configured in your repository
5. **Environment Variables**: Project-specific env vars need customization
6. **Path References**: Some paths may be specific to the original project structure

## How to Integrate These Workflows

### Step 1: Create Your Workflows Directory
```bash
mkdir -p .github/workflows
```

### Step 2: Copy and Adapt Workflows
For each workflow you want to use:

1. Copy the workflow file to `.github/workflows/`
2. Replace ALL placeholder values:
   - `$GCP_PROJECT_ID` → Your GCP project ID (e.g., `my-project-123`)
   - `$GITHUB_REPOSITORY` → Your repo (e.g., `myorg/myrepo`)
   - `$GITHUB_OWNER` → Your GitHub username or organization
   - `$USER` → Your username if applicable

3. Configure required secrets in your repository settings:
   - `GITHUB_TOKEN` (usually automatic)
   - `GCP_SERVICE_ACCOUNT` if using GCP deployments
   - Any API keys referenced in the workflow

### Step 3: Validate Before Committing
```bash
# Check YAML syntax
yamllint .github/workflows/*.yml

# Or use actionlint for GitHub Actions specific validation
actionlint
```

## Workflow Categories

### CI/CD Workflows
- **test.yml** - Run tests on push/PR
- **deploy-*.yml** - Deployment workflows
- **presubmit.yml** - Pre-merge validation

### Automation Workflows
- **pr-cleanup.yml** - Automatic PR maintenance
- **auto-deploy-*.yml** - Automatic deployment triggers
- **slash-dispatch.yml** - Slash command dispatching

### Code Quality
- **hook-tests.yml** - Claude Code hook validation
- **doc-size-check.yml** - Documentation size limits

## Common Adaptations

### For Google Cloud Deployments
```yaml
# Replace this:
env:
  GCP_PROJECT: $GCP_PROJECT_ID

# With your actual project:
env:
  GCP_PROJECT: my-actual-project-id
```

### For Repository References
```yaml
# Replace this:
repository: $GITHUB_REPOSITORY

# With your repo:
repository: myorg/myrepo
```

### For Service Account Authentication
Set up Workload Identity Federation or use a service account key:
```yaml
- uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/YOUR_POOL/providers/YOUR_PROVIDER
    service_account: YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com
```

## Need Help?

Claude Code can assist with adapting these workflows to your specific project. Just describe your CI/CD requirements and ask for help customizing the relevant workflow files.

---

**Source**: Exported from [Your Project](https://github.com/$GITHUB_REPOSITORY) Claude Code configuration
