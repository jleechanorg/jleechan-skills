---
name: cloud-ops-credential-guard
description: Securely guide teammates through cloud configuration, secrets management, and incident triage
type: usage
scope: project
---

# Cloud Ops & Credential Guard

## Purpose
Guide Claude in helping teammates configure and troubleshoot cloud integrations securely without exposing sensitive data.

## Trigger phrases
- Questions about Firebase, Gemini, or other API credentials.
- Requests for deployment configuration or secure credential setup.
- Incident triage involving auth failures or clock drift.

## Configuration checklist
1. **Secrets handling**
   - Never read, create, edit, or commit `.env` files. Keep credentials in the process environment, macOS Keychain, or the designated secret manager.
   - Do not add new environment variables unless the task explicitly requests them; use existing documented configuration.
2. **Firebase setup**
   - Place `serviceAccountKey.json` under a secure, ignored path (see `.gitignore`).
   - Confirm the Firestore project ID from active process or authorized service configuration; never inspect `.env`.
   - Validate clock sync with `ntpstat` or `timedatectl` when auth tokens fail.
3. **Gemini API**
   - Use an existing authorized Gemini credential from the designated secure store; credential creation, rotation, or revocation requires explicit authorization.
   - Follow the owning repository's test contract for provider selection; do not introduce mock services into real-service test directories.
4. **MCP/Claude bots**
   - Run `./claude_mcp.sh` or `./start_game_mcp.sh` after confirming active process configuration without reading `.env`.
   - Use `./kill_dev_server.sh` to reset stale sockets before re-authenticating.

## Troubleshooting flow
1. Collect error logs from `latest_ci_logs.txt` or service console.
2. Identify whether failures stem from missing env vars, expired tokens, or network restrictions.
3. Suggest verification commands that report credential presence or identity without printing secret values. Never read from `.env`.
4. Use existing authorized credentials for in-scope work. Request the user only for credential creation, rotation, revocation, or a required physical authentication step; never suggest changing `.env` as routine remediation.

## Security reminders
- Never request or display `.env` contents; use redacted examples based on the approved secure configuration mechanism.
- Use only the test mode permitted by the owning repository's service-boundary contract.
- Verify `.gitignore` contains credential files before advising users to create them.
- Point teammates to `docs/security/` and `README.md#configuration` for full policies.

## Response structure
1. Restate the issue in security-aware language.
2. Outline the checklist items relevant to the scenario.
3. Provide commands or file paths for verification.
4. Close with preventative tips (secret rotation cadence, access controls, etc.).
