# GCP Deployments Reference

## Project Information
- **GCP Project**: `worldarchitecture-ai`
- **Region**: `us-central1`

## Deployed Services

### Development Environment (mvp-site-app-dev)
- **Service Name**: `mvp-site-app-dev`
- **URL**: https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/
- **Current Revision**: `mvp-site-app-dev-00084-2t9`
- **Last Deployed**: 2025-08-30 17:23:11
- **Image SHA**: `sha256:6977cf297ece931d6ef2eb5e9849762780ceffc9992da46fd602ee60cf2b8c6d`
- **Status**: ⚠️ Very outdated (3+ months behind main)

### Stable/Production Environment (mvp-site-app-stable)
- **Service Name**: `mvp-site-app-stable`
- **URL**: https://mvp-site-app-stable-i6xf2p72ka-uc.a.run.app/
- **Test URL**: https://test---mvp-site-app-stable-i6xf2p72ka-uc.a.run.app
- **Current Revision**: `mvp-site-app-stable-00055-bpr`
- **Last Deployed**: 2025-11-12 01:02:59
- **Image SHA**: `sha256:69879c67d6d16252585031b10067e64ee548e65f4ac8803d43e11ae5083751e0`
- **Git Commit**: `2e881735d` - "fix: remove default rate limits to prevent CSS/JS loading failures"
- **Status**: ✅ Working (10 commits behind main)

### Staging Environment (mvp-site-app-staging)
- **Status**: ✅ Available via deploy.sh
- **URL**: https://mvp-site-app-staging-i6xf2p72ka-uc.a.run.app
- **Purpose**: Safe iteration environment for testing fixes without affecting dev/stable

## Current Main Branch
- **Latest Commit**: `7809a215c` - "Fix all rate limits - increase to sanity-check thresholds"
- **Commits Ahead of Stable**: 10 commits

## Key Commits (Post-Stable Deployment)

1. `7809a215c` - Fix all rate limits - increase to sanity-check thresholds (#2018)
2. `ed4d1e959` - Clarify agent directives in processmsgs command (#2017)
3. `cb779920b` - Fix auth script path in secondo-cli.sh (#2013)
4. `ff798af6d` - Sync improvements from global ~/.claude configuration (#2012)
5. `caf1d3124` - Revert gh CLI installation hooks (#2011)
6. `665b68556` - Add npm installation instructions to claude.md (#2002)
7. `e95c5eb43` - fix: reduce max instances to 6 and fix deploy script gcloud flag (#2001)
8. `cb77f0d14` - Clarify copilot slash command documentation (#2009)
9. `2fc3e1e73` - Set up hook method for GitHub CLI installation (#2003)
10. `12784dd69` - docs: add git submodule slash command path to CLAUDE.md (#1999)

## CSS Issue History

### Original Introduction (Sep 21, 2025 - Commit defc63897)
- **Commit**: `defc63897` - "🚨 CRITICAL SECURITY FIXES: Production-ready security hardening"
- **Purpose**: Security hardening to prevent DoS/financial attacks
- **Configuration Added**:
  ```python
  default_limits=["200 per day", "50 per hour", "10 per minute"]
  ```
- **Unintended Consequence**: 10/min limit applied to ALL routes including static CSS/JS

### The Problem (Sep 21 - Nov 12, 2025)
- **Root Cause**: Aggressive default rate limits (10 per minute) blocked parallel browser requests for static assets
- **Symptom**: 429 errors when loading multiple CSS/JS files
- **Impact**: HTML error pages returned instead of CSS/JS, causing MIME type errors
- **Duration**: ~2 months of CSS loading issues in production

### The Fix (Commit 2e881735d - Nov 11, 2025)
- Removed default_limits from Flask-Limiter configuration
- Static files and frontend routes completely unrate-limited
- Added explicit rate limits only to API routes needing protection
- **Status**: ✅ Deployed to stable, working correctly

### Latest Enhancement (Commit 7809a215c - Nov 14, 2025)
- Increased rate limits to sanity-check thresholds
- Changed from restrictive limits to high thresholds (e.g., 30000/hour, 1000/min)
- **Status**: ⚠️ Not yet deployed to any environment

## Quick Reference Commands

### List All Services
```bash
gcloud run services list --platform managed --format="table(name,region,status)"
```

### Get Service Details
```bash
# Dev environment
gcloud run services describe mvp-site-app-dev --region us-central1

# Stable environment
gcloud run services describe mvp-site-app-stable --region us-central1
```

### Get Current Deployment Commit
```bash
# Find image SHA
gcloud run services describe mvp-site-app-stable --region us-central1 \
  --format="value(spec.containers[0].image)"

# List recent image tags
gcloud container images list-tags gcr.io/worldarchitecture-ai/mvp-site-app \
  --limit=20 --format="table(digest,tags,timestamp)"
```

### Deploy to Environment
```bash
# From project root
./deploy.sh mvp_site dev      # Deploy to dev
./deploy.sh mvp_site staging  # Deploy to staging
./deploy.sh mvp_site stable   # Deploy to stable/production

# Or from mvp_site directory (note: no '.' needed when in app directory)
cd "$SOURCE_DIR"
../deploy.sh dev      # Deploy to dev
../deploy.sh staging  # Deploy to staging
../deploy.sh stable   # Deploy to stable/production
```

### Manual Staging Deployment (Advanced)
```bash
# Use deploy.sh for normal deployments (recommended)
# Manual deployment (if needed for debugging):
cd "$SOURCE_DIR"
gcloud builds submit . --tag gcr.io/worldarchitecture-ai/mvp-site-app:staging
gcloud run deploy mvp-site-app-staging \
  --image gcr.io/worldarchitecture-ai/mvp-site-app:staging \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory=2Gi \
  --timeout=300s \
  --min-instances=1 \
  --max-instances=6 \
  --concurrency=10
```

## Deployment Architecture

```
Git Commits
     ↓
Cloud Build (automatic on deploy.sh)
     ↓
Container Registry (gcr.io/worldarchitecture-ai/mvp-site-app)
     ↓
Cloud Run Services
     ├── mvp-site-app-dev (outdated - Aug 30)
     ├── mvp-site-app-staging (✅ available - latest main)
     └── mvp-site-app-stable (production - 10 commits behind)
```

## Notes
- Dev environment is significantly outdated (Aug 30 vs current Nov 14)
- Stable is 10 commits behind main branch
- Staging environment (`mvp-site-app-staging`) is now available for safe iteration
- CSS loading issues were fixed in commit 2e881735d (deployed to stable and staging)
- Latest rate limit improvements in 7809a215c deployed to staging, not yet on stable
