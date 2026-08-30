---
description: /deploy
type: llm-orchestration
execution_mode: immediate
---
# /deploy

Run the target repository's deployment entrypoint only after confirming the
repository and requested environment.

1. Change to the repository root.
2. Look for `./deploy.sh`, then `./scripts/deploy.sh`.
3. If neither exists, report that the repository has no supported deployment
   entrypoint; do not substitute a package-local script.
4. Run the discovered script with any requested arguments, respecting its
   executable bit or invoking it with `bash`.

This package provides command guidance only; it does not ship a deploy launcher.
