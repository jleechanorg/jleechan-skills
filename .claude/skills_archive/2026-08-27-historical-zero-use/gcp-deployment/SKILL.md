# GCP Deployment & Server Management

**Purpose**: Guide for finding GCP Cloud Run services and deploying Your Project

⚠️ **IMPORTANT**: This skill is **ONLY** for the Your Project repository and GCP project. The deployment scripts, service names, and configurations are specific to this project and will not work for other repositories or GCP projects.

## Project Overview

**Repository**: https://github.com/jleechanorg/your-project.com
**Project**: Your Project
**GCP Project ID**: `worldarchitecture-ai` (specific to this project only)
**Region**: `us-central1`
**Platform**: Google Cloud Run (containerized deployments)

**Scope**: All commands, scripts, and service references in this document are specific to the `worldarchitecture-ai` GCP project and will not work with other GCP projects or repositories.

---

## 🎯 Quick Reference

### Service URLs

| Environment | Service Name | URL |
|-------------|--------------|-----|
| **Production** | mvp-site-app-stable | https://mvp-site-app-stable-i6xf2p72ka-uc.a.run.app |
| **Staging** | mvp-site-app-staging | https://mvp-site-app-staging-i6xf2p72ka-uc.a.run.app |
| **Development** | mvp-site-app-dev | https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app |
| **PR Preview** | mvp-site-app-s1 through s10 | Rotating pool (see PR Preview section below) |

### Health Check Endpoints

Add `/health` to any service URL:
- Production: https://mvp-site-app-stable-i6xf2p72ka-uc.a.run.app/health
- Staging: https://mvp-site-app-staging-i6xf2p72ka-uc.a.run.app/health
- Dev: https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/health

---

## 🔍 Finding GCP Services

### Method 1: Cloud Console (Web UI)

1. **Navigate to Cloud Run**:
   ```
   https://console.cloud.google.com/run?project=worldarchitecture-ai
   ```

2. **Filter by service name**: Look for `mvp-site-app*` services

3. **View service details**: Click on any service to see:
   - Service URL
   - Revisions
   - Configuration
   - Logs
   - Metrics

### Method 2: gcloud CLI

```bash
# List all Cloud Run services
gcloud run services list \
  --project=worldarchitecture-ai \
  --region=us-central1

# Get specific service details
gcloud run services describe mvp-site-app-stable \
  --project=worldarchitecture-ai \
  --region=us-central1 \
  --format=yaml

# Get service URL
gcloud run services describe mvp-site-app-stable \
  --project=worldarchitecture-ai \
  --region=us-central1 \
  --format="value(status.url)"
```

### Method 3: From Repository

The deployment script automatically determines the correct service:

```bash
# Check what will be deployed
cat scripts/deploy_common.sh | grep -A 10 "SERVICE_NAME="
```

Service naming pattern:
- Dev: `mvp-site-app-dev`
- Staging: `mvp-site-app-staging`
- Production: `mvp-site-app-stable`

---

## 🚀 Deployment Methods

### Deployment Decision Tree

```
Need to deploy?
├─ Production/Stable? → Use GitHub Actions (Required)
├─ Staging? → Use ./deploy.sh staging (local deployment)
└─ Development? → Use ./deploy.sh (local) OR auto-deploys on push to main
```

### Method 1: Local Deployment (Dev/Staging Only)

**Development (Default)**:
```bash
./deploy.sh
# OR explicitly
./deploy.sh mvp_site
```

**Staging**:
```bash
./deploy.sh mvp_site staging
```

**Production** (BLOCKED locally):
```bash
./deploy.sh mvp_site stable
# ❌ This will fail with safety message directing you to GitHub Actions
```

**Auto-detection**:
The script automatically detects deployable apps if run from project root:
```bash
# If current directory has Dockerfile, uses current directory
# Otherwise shows interactive menu of available apps
./deploy.sh
```

### Method 2: GitHub Actions (Production & Development)

#### Production/Stable Deployment (Required Method)

**Via CLI**:
```bash
# Trigger production deployment
gh workflow run deploy-production.yml \
  -f confirm_production="DEPLOY TO PRODUCTION"

# Check deployment status
gh run list --workflow=deploy-production.yml --limit 1
gh run view <run-id>
```

**Via GitHub Web UI**:
1. Go to: https://github.com/jleechanorg/your-project.com/actions/workflows/deploy-production.yml
2. Click "Run workflow"
3. Type "DEPLOY TO PRODUCTION" in confirmation field
4. Click "Run workflow"
5. Wait for approval (protected environment)
6. Deployment proceeds after approval

**Why GitHub Actions Required for Production**:
- ✅ Proper approval process
- ✅ Full audit trail
- ✅ Prevents accidental deployments
- ✅ Team visibility
- ✅ Protected environment with manual approval gate

#### Auto-Deploy on Push to Main (Development)

Development environment auto-deploys when code is pushed to `main` branch:

**Workflow**: `.github/workflows/auto-deploy-dev.yml`

**Trigger**:
```bash
git push origin main
# Automatically triggers deployment to dev environment
```

**Check auto-deploy status**:
```bash
gh run list --workflow=auto-deploy-dev.yml --limit 3
```

---

## 📋 Deployment Script Details

### Main Script: `./deploy.sh`

**Location**: Project root
**Purpose**: Context-aware deployment with auto-detection

**Usage**:
```bash
./deploy.sh [TARGET_DIR] [ENVIRONMENT]
```

**Examples**:
```bash
# Deploy from current directory to dev (if Dockerfile exists)
./deploy.sh

# Deploy specific app to dev
./deploy.sh mvp_site

# Deploy to staging
./deploy.sh mvp_site staging

# Attempt production (will be blocked)
./deploy.sh mvp_site stable
```

**Environment Mapping**:
- `dev` (default): Development environment
- `staging`: Staging environment
- `stable`, `prod`, `production`: Production (GitHub Actions only)

### Helper Script: `scripts/deploy_common.sh`

**Purpose**: Shared deployment logic
**Contains**:
- Service name mapping
- GCP configuration
- Cloud Build submission
- Autoscaling settings

**Service Name Logic**:
```bash
if [[ "$ENVIRONMENT" == "stable" ]]; then
    SERVICE_NAME="mvp-site-app-stable"
elif [[ "$ENVIRONMENT" == "staging" ]]; then
    SERVICE_NAME="mvp-site-app-staging"
else
    SERVICE_NAME="mvp-site-app-dev"
fi
```

---

## 🔧 Configuration Details

### Autoscaling

**Current Settings** (all environments):
- **Max Instances**: 6
- **Min Instances**: 0 (scales to zero when not in use)

**Why 6 instances**:
- Sanity-check threshold to prevent runaway costs
- Adequate for current traffic patterns
- Can be adjusted in `deploy.sh` (MAX_INSTANCES variable)

### Environment Variables

**Set via GCP Console**:
1. Navigate to service in Cloud Run
2. Click "Edit & Deploy New Revision"
3. Go to "Variables & Secrets" tab
4. Add/modify environment variables

**Common variables**:
- `GEMINI_API_KEY`: Google Gemini API key
- `FIREBASE_CREDENTIALS`: Firebase service account JSON
- Environment-specific configs

### Cloud Build

**Build timeout**: 10 minutes (configurable)
**Build logs**: Streamed to terminal during deployment
**Build configuration**: Defined in `Dockerfile` in target directory

---

## 📊 Monitoring & Logs

### View Logs

**Via Console**:
```
# Production logs
https://console.cloud.google.com/logs/query?project=worldarchitecture-ai&query=resource.type%3D%22cloud_run_revision%22%0Aresource.labels.service_name%3D%22mvp-site-app-stable%22

# Staging logs
https://console.cloud.google.com/logs/query?project=worldarchitecture-ai&query=resource.type%3D%22cloud_run_revision%22%0Aresource.labels.service_name%3D%22mvp-site-app-staging%22

# Dev logs
https://console.cloud.google.com/logs/query?project=worldarchitecture-ai&query=resource.type%3D%22cloud_run_revision%22%0Aresource.labels.service_name%3D%22mvp-site-app-dev%22
```

**Via gcloud CLI**:
```bash
# Stream production logs
gcloud run services logs read mvp-site-app-stable \
  --project=worldarchitecture-ai \
  --region=us-central1 \
  --limit=50

# Follow logs in real-time
gcloud run services logs tail mvp-site-app-stable \
  --project=worldarchitecture-ai \
  --region=us-central1
```

### Check Service Health

```bash
# Production health check
curl https://mvp-site-app-stable-i6xf2p72ka-uc.a.run.app/health

# Staging health check
curl https://mvp-site-app-staging-i6xf2p72ka-uc.a.run.app/health

# Dev health check
curl https://mvp-site-app-i6xf2p72ka-uc.a.run.app/health
```

**Expected response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-14T18:35:44Z"
}
```

---

## 🛡️ Safety Features

### Production Deployment Protection

**Local deployment blocked**:
```bash
./deploy.sh mvp_site stable
# Output:
# 🚨 PRODUCTION DEPLOYMENT BLOCKED 🚨
# Production deployments are NOT allowed from local machines for safety.
```

**GitHub Actions protection**:
- Protected environment: `production`
- Manual approval required
- Input validation: Must type "DEPLOY TO PRODUCTION"
- Full audit trail in GitHub Actions

### Deployment Validation

**Pre-deployment checks**:
1. Dockerfile exists in target directory
2. Valid environment specified
3. GCP authentication configured (GitHub Actions)
4. Service name correctly mapped

**Post-deployment checks**:
1. Service deployed successfully
2. Health endpoint returns 200 OK
3. Revision created and serving traffic

---

## 🔑 Authentication

### Local Development

**GCP Authentication**:
```bash
# Login to GCP
gcloud auth login

# Set project
gcloud config set project worldarchitecture-ai

# Verify authentication
gcloud auth list
```

### GitHub Actions

**Authentication**: Workload Identity Federation
**Service Account**: `github-actions@worldarchitecture-ai.iam.gserviceaccount.com`
**Configured in**: `.github/workflows/*.yml`

**Secrets required**:
- `GCP_WORKLOAD_IDENTITY_PROVIDER`: Workload identity provider
- `GCP_SERVICE_ACCOUNT`: Service account email

---

## 📚 Common Tasks

### Deploy to Production

```bash
# 1. Trigger deployment
gh workflow run deploy-production.yml \
  -f confirm_production="DEPLOY TO PRODUCTION"

# 2. Monitor deployment
gh run list --workflow=deploy-production.yml --limit 1

# 3. View detailed logs
gh run view <run-id>

# 4. Verify health
curl https://mvp-site-app-stable-i6xf2p72ka-uc.a.run.app/health
```

### Deploy to Staging

```bash
# Local deployment (staging uses local deployment only)
./deploy.sh mvp_site staging
```

### Deploy to Development

```bash
# Option 1: Local deployment
./deploy.sh mvp_site

# Option 2: Push to main (auto-deploys)
git push origin main

# Option 3: Manual GitHub Actions trigger
gh workflow run auto-deploy-dev.yml
```

### Check Current Deployment

```bash
# List all services
gcloud run services list \
  --project=worldarchitecture-ai \
  --region=us-central1

# Get specific service status
gcloud run services describe mvp-site-app-stable \
  --project=worldarchitecture-ai \
  --region=us-central1

# Check recent deployments
gh run list --workflow=deploy-production.yml --limit 5
```

### Rollback Deployment

```bash
# List revisions
gcloud run revisions list \
  --service=mvp-site-app-stable \
  --project=worldarchitecture-ai \
  --region=us-central1

# Route traffic to previous revision
gcloud run services update-traffic mvp-site-app-stable \
  --to-revisions=<REVISION-NAME>=100 \
  --project=worldarchitecture-ai \
  --region=us-central1
```

---

## 🐛 Troubleshooting

### Deployment Fails

**Check build logs**:
```bash
# View recent Cloud Build logs
gcloud builds list \
  --project=worldarchitecture-ai \
  --limit=5

# Get specific build details
gcloud builds describe <BUILD-ID> \
  --project=worldarchitecture-ai
```

### Service Not Responding

**Check service status**:
```bash
gcloud run services describe mvp-site-app-stable \
  --project=worldarchitecture-ai \
  --region=us-central1 \
  --format=yaml
```

**Check logs**:
```bash
gcloud run services logs read mvp-site-app-stable \
  --project=worldarchitecture-ai \
  --region=us-central1 \
  --limit=100
```

### Authentication Issues

**Local**:
```bash
# Re-authenticate
gcloud auth login
gcloud auth application-default login

# Verify project
gcloud config get-value project
```

**GitHub Actions**:
- Check Workload Identity Federation configuration
- Verify service account permissions
- Review workflow run logs for auth errors

---

## 📖 Additional Resources

### Documentation Links

- **Cloud Run Console**: https://console.cloud.google.com/run?project=worldarchitecture-ai
- **Cloud Build Console**: https://console.cloud.google.com/cloud-build?project=worldarchitecture-ai
- **GitHub Actions**: https://github.com/jleechanorg/your-project.com/actions
- **GCP Logs**: https://console.cloud.google.com/logs?project=worldarchitecture-ai

### Related Files

- **Main deployment script**: `./deploy.sh`
- **Common deployment logic**: `scripts/deploy_common.sh`
- **Production workflow**: `.github/workflows/deploy-production.yml`
- **Auto-deploy workflow**: `.github/workflows/auto-deploy-dev.yml`

### Contact & Support

- **Repository**: https://github.com/jleechanorg/your-project.com
- **Issues**: https://github.com/jleechanorg/your-project.com/issues

---

## 🎓 Best Practices

1. **Always test in dev/staging first** before production
2. **Use health checks** to verify deployments
3. **Monitor logs** during and after deployment
4. **Keep autoscaling limits** reasonable to control costs
5. **Use GitHub Actions** for production deployments
6. **Tag releases** when deploying to production
7. **Document environment variables** in team docs
8. **Review Cloud Run metrics** regularly

---

---

## 🔍 PR Preview Deployments

### Overview

PR preview deployments are automatically created for pull requests via the "Deploy PR Preview (Rotating Pool)" workflow. These deployments use a rotating pool of services (`mvp-site-app-s1` through `mvp-site-app-s10`) to provide isolated preview environments for testing PR changes.

### Finding PR Preview URLs

#### Method 1: From GitHub Actions (Recommended)

**Get URL from latest PR preview deployment**:
```bash
# Get the latest PR preview deployment run
RUN_ID=$(gh run list --workflow="Deploy PR Preview (Rotating Pool)" --limit=1 --json databaseId -q '.[0].databaseId')

# Extract deployment URL from logs
gh run view --log "$RUN_ID" | grep "PREVIEW_URL:" | grep -oE "https://[^[:space:]]+\.run\.app"
```

**Get URL for specific PR**:
```bash
# Find deployment run for PR #3490
gh run list --workflow="Deploy PR Preview (Rotating Pool)" --limit=50 --json databaseId,displayTitle | \
  python3 -c "import sys, json; runs = json.load(sys.stdin); \
  matches = [r for r in runs if '3490' in r.get('displayTitle', '')]; \
  print(matches[0]['databaseId'] if matches else 'No matching runs found')"

# Then get URL from that run's logs
gh run view --log <RUN_ID> | grep "PREVIEW_URL:"
```

> **Note:** If no matching runs are found, increase the `--limit` value or verify the PR number. The defensive Python snippet above will print "No matching runs found" instead of raising an `IndexError`.

#### Method 2: From gcloud (Current Service)

**List all PR preview services**:
```bash
gcloud run services list \
  --project=worldarchitecture-ai \
  --region=us-central1 \
  --filter="name:mvp-site-app-s*" \
  --format="table(name,status.url,metadata.labels.`pr-number`)"
```

**Get URL for specific PR**:
```bash
# Find service for PR #3490
gcloud run services list \
  --project=worldarchitecture-ai \
  --region=us-central1 \
  --filter="metadata.labels.`pr-number`=3490" \
  --format="value(status.url)"
```

**Get URL for specific service (e.g., s8)**:
```bash
gcloud run services describe mvp-site-app-s8 \
  --project=worldarchitecture-ai \
  --region=us-central1 \
  --format="value(status.url)"
```

#### Method 3: From PR Comments

PR preview deployments automatically post comments on the PR with the deployment URL. Check the PR's comment thread for the deployment link.

### PR Preview Service Naming

- **Pattern**: `mvp-site-app-s{1-10}`
- **Example**: `mvp-site-app-s8` (for PR #3490)
- **Rotation**: Services are reused across different PRs
- **Labels**: Each service has `pr-number` label indicating which PR it's currently serving

### Checking PR Preview Deployment Status

```bash
# Check if PR has a preview deployment
gh pr view <PR_NUMBER> --json number,headRefName

# List recent PR preview deployments
gh run list --workflow="Deploy PR Preview (Rotating Pool)" --limit=10

# View specific deployment run
gh run view <RUN_ID> --log | grep -E "(PREVIEW_URL|Service URL|Deployment URL)"
```

### PR Preview Health Checks

```bash
# Health check for s8 (example)
curl https://mvp-site-app-s8-i6xf2p72ka-uc.a.run.app/health

# Or get URL dynamically
S8_URL=$(gcloud run services describe mvp-site-app-s8 \
  --project=worldarchitecture-ai \
  --region=us-central1 \
  --format="value(status.url)")
curl "${S8_URL}/health"
```

### Notes

- PR preview deployments are **temporary** and may be cleaned up or reused
- Each PR gets assigned to an available service from the pool (s1-s10)
- The same service may serve different PRs over time
- Always check the `pr-number` label to confirm which PR a service is currently serving
- PR preview URLs are also posted as comments on the PR

---

**Last Updated**: 2026-01-12
**Version**: 1.1
