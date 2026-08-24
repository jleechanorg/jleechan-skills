---
description: /localserver
type: llm-orchestration
execution_mode: immediate
---
# /localserver

Start a local server only through the target repository's documented entrypoint.

1. Change to the repository root.
2. Look for `./run_local_server.sh`, then `./scripts/run_local_server.sh`.
3. If neither exists, report that no supported local-server launcher was found;
   do not substitute a package-local script.
4. Run the discovered script with any requested arguments, respecting its
   executable bit or invoking it with `bash`.

This package provides command guidance only; it does not ship a local-server launcher.
