---
description: /arch Command - MVP-focused architecture review
---
Review the architecture of the target given in the arguments (a PR, branch, path or design) for a solo developer shipping an MVP: read the actual code and docs (for a PR, list its real files with `gh api repos/<owner>/<repo>/pulls/<PR#>/files --jq '.[].filename'` and check that claimed features are implemented, not only documented), then report module boundaries, coupling, over-engineering, scalability limits and real security or correctness risks, each with file:line evidence and a concrete recommendation.
