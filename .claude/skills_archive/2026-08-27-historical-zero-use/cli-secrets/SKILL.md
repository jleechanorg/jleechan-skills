---
name: cli-secrets
description: "Use when debugging unauthorized/fallback errors. Flags redacted placeholders (e.g. __OPENCLAW_REDACTED__) as invalid tokens; checks env overrides first."
---

# CLI secrets — never export redacted placeholders (Hermes gateway and similar)


Some CLIs **intentionally redact** secrets in `config get` output (e.g. `__OPENCLAW_REDACTED__` in legacy configs). That string is **not** a valid token.

- **Do not** export legacy gateway tokens without verifying the value is a real secret, not a redaction sentinel.
- **Hermes** uses its own auth at `~/.hermes_prod/config.yaml` — do not confuse Hermes auth with the legacy OpenClaw auth tokens.
- When debugging “unauthorized” / “falling back to embedded”, check env overrides **first** — stale exported redacted tokens are a common root cause.
