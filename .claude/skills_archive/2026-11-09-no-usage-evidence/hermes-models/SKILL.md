---
name: hermes-models
description: Use when inspecting, selecting, changing, or diagnosing Claude wrapper and Hermes model configuration on either host.
type: reference
---

# Host-aware model configuration

Never copy a dated model map or assume both hosts match. Never store or retrieve secrets from `.env` files.

## Canonical live owners

- Claude wrapper definitions and route enablement: live `~/.bashrc` (read-only unless the user explicitly authorizes edits).
- Hermes model/provider: live `~/.hermes/config.yaml`.
- Credentials: approved process environment or macOS Keychain; never `~/.hermes/.env`.
- AO model shorthands: live `~/.hermes/agent-orchestrator.yaml`.

The current Mac snapshot on 2026-07-31 has OpenRouter shell routes explicitly disabled in `~/.bashrc` and Hermes configured for provider `minimax`, model `MiniMax-M3`. Treat this only as a dated observation; re-read the live owners before every claim or change.

## Read-only discovery

```bash
rg -n '^claude[a-z]*\\(\\)|OpenRouter|OR_PROXY_DISABLED' ~/.bashrc
rg -n '^(model:|  default:|  provider:)' ~/.hermes/config.yaml
rg -n 'modelByCli|provider' ~/.hermes/agent-orchestrator.yaml
test -n "${MINIMAX_API_KEY:-}"
security find-generic-password -s openrouter-pilot-api-key >/dev/null 2>&1
```

Do not print secret values. An absent environment variable alone does not prove missing credentials; follow the global two-probe authentication rule before recommending login.

## Change protocol

1. State the exact host, live owner, current provider/model, intended provider/model, and user-visible reason.
2. Probe the target provider/model with a minimal non-UI request using an already-loaded credential; record HTTP/provider status without printing the credential.
3. Ask before changing model, credential source, wrapper, path, or default configuration.
4. Make the smallest owner-file change. Never edit `~/.bashrc` wrappers without explicit user authorization.
5. On service start, stop, or restart, inspect the process table and prove every old instance is dead before launching a replacement.
6. Never run prod and staging gateways concurrently when they share Slack credentials.
7. Verify from the user layer: process identity, Hermes health/status, provider/model shown by live config, and one cheap real request.

## Diagnosis

- A TUI model/auth message is not enough to edit wrappers or recommend login.
- For a previously working OpenRouter route, probe the Keychain entry and a cheap provider request before changing configuration.
- For MiniMax plan errors, preserve the configured model and report the exact provider error; do not silently substitute another provider.
- Treat `~/.bashrc` route-disable declarations as authoritative until the user explicitly changes them.
