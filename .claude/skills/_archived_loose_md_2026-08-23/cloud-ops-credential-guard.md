---
description: Securely guide teammates through cloud configuration, secrets management, and incident triage
type: usage
scope: project
---

# Cloud Ops & Credential Guard

## Purpose
Guide Claude in helping teammates configure and troubleshoot cloud integrations securely without exposing sensitive data.

## Trigger phrases
- Questions about Firebase, Gemini, or other API credentials.
- Requests for deployment environment setup or `.env` configuration.
- Incident triage involving auth failures or clock drift.

## Configuration checklist
1. **Secrets handling**
   - Never commit real keys; store them in `.env` or platform secret managers.
   - Reference `.env.example` for required variables; add new ones there before documenting publicly.
2. **Firebase setup**
   - Place `serviceAccountKey.json` under a secure, ignored path (see `.gitignore`).
   - Confirm Firestore project ID matches `FIREBASE_PROJECT_ID` in `.env`.
   - Validate clock sync with `ntpstat` or `timedatectl` when auth tokens fail.
3. **Gemini API**
   - Export `GEMINI_API_KEY` locally and in deployment secrets.
   - For local tests, prefer mock adapters enabled via `TEST_MODE=mock`.
4. **MCP/Claude bots**
   - Run `./claude_mcp.sh` or `./start_game_mcp.sh` after confirming `.env` values.
   - Use `./kill_dev_server.sh` to reset stale sockets before re-authenticating.

## Troubleshooting flow
1. Collect error logs from `latest_ci_logs.txt` or service console.
2. Identify whether failures stem from missing env vars, expired tokens, or network restrictions.
3. Suggest verification commands:
   ```bash
   grep KEY_NAME .env
   ls -al ~/.config/gcloud
   firebase login:list
   ```
4. Recommend safe remediation (reissue keys, rotate secrets, update `.env`), emphasizing not to paste secrets into chat.

## Security reminders
- Offer redacted examples when showing `.env` entries.
- Encourage using mock services or feature flags during demos.
- Verify `.gitignore` contains credential files before advising users to create them.
- Point teammates to `docs/security/` and `README.md#configuration` for full policies.

## Response structure
1. Restate the issue in security-aware language.
2. Outline the checklist items relevant to the scenario.
3. Provide commands or file paths for verification.
4. Close with preventative tips (secret rotation cadence, access controls, etc.).
