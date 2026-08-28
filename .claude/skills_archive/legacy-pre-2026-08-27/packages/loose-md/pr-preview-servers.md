# PR Preview Servers — GCP Cloud Run Pool

Reference for the rotating preview server pool used to deploy PR branches.

## Pool Configuration

- **Pool size**: 10 servers (`mvp-site-app-s1` through `mvp-site-app-s10`)
- **Service prefix**: `mvp-site-app`
- **GCP project**: `worldarchitecture-ai`
- **Region**: `us-central1`
- **Trigger**: Any PR push to `$PROJECT_ROOT/**`, `Dockerfile`, `requirements.txt`, etc.
- **Workflow**: `.github/workflows/pr-preview.yml`
- **Pool assignment script**: `.github/scripts/pr-server-pool.sh`

## URL Pattern

```
https://mvp-site-app-s{N}-{hash}-uc.a.run.app
```

Where `{N}` is 1–10 and `{hash}` is Cloud Run's stable unique URL segment.

### Finding the Current PR's Preview URL

**From GitHub CLI (fastest):**
```bash
gh pr view <PR_NUMBER> --json comments --jq '.comments[].body' | grep -o 'https://mvp-site-app-s[^ ]*'
```

**From PR comments in the UI:**
Look for the bot comment that says "Preview deployed to: `https://...`"

**From Cloud Run directly:**
```bash
gcloud run services describe mvp-site-app-s{N} \
  --project=worldarchitecture-ai \
  --region=us-central1 \
  --format='value(status.url)'
```

## Deployment Details

The preview server is deployed with:
- `FLASK_ENV=production`
- `ENVIRONMENT=preview`
- Secrets: `GEMINI_API_KEY`, `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`
- **NO** `TESTING_AUTH_BYPASS=true` — real Firebase auth is required for protected endpoints
- Max 2 Cloud Run instances, same timeout as production

## Health Endpoint

```
GET /health
→ 200 {"status": "healthy", "service": "worldarchitect-ai", "timestamp": "..."}
```

Note: `/health` does **not** expose the `ENVIRONMENT` env var. Confirmed 2026-02-20.

## Testing Against Preview Servers

Use the standalone smoke test (no local server startup needed):

```bash
# Test the current PR's preview server
python3 testing_mcp/test_openclaw_gateway_url_preview.py

# Test a specific preview URL
python3 testing_mcp/test_openclaw_gateway_url_preview.py \
  --server-url https://mvp-site-app-s10-i6xf2p72ka-uc.a.run.app
```

### What You Can Test Without Auth

| Test | Why |
|------|-----|
| `/health` → 200 | Public health endpoint |
| `/settings` HTML → 200, field present | Public HTML page |
| `POST /api/settings` → 401 (not 404) | Route wired, auth enforced |
| Static assets | Public static files |

### What Requires Real Firebase Auth

- `POST /api/settings` with actual settings values (save to Firestore)
- `GET /api/settings` (read user settings)
- Any campaign API endpoint

## Pool Eviction Policy

When all 10 slots are taken, the oldest assignment is evicted to make room.
The evicted PR loses its preview URL. Check PR #N's comments for current status.

## Known Preview Server URLs by PR

| PR | Server | URL |
|----|--------|-----|
| #5662 | s10 | `https://mvp-site-app-s10-i6xf2p72ka-uc.a.run.app` |
| #5857 | s2  | `https://mvp-site-app-s2-i6xf2p72ka-uc.a.run.app` |

> Update this table as PRs are deployed. URL stays stable as long as the pool slot isn't evicted.
