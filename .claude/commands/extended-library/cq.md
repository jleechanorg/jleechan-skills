---
description: Alias for /code-quality
type: quality
execution_mode: immediate
---
# /cq

Thin alias for `/code-quality`.

Load and follow `.claude/skills/code-quality/SKILL.md`, passing any command arguments through as the review scope. Preserve `/code-quality` behavior: Short variant for small PRs, Long variant for important / architectural / AI-generated PRs, file:line evidence for every finding.
