---
name: metric-policy-wiring
description: "Use when adding/changing a metric (zero-touch, smoothness, etc.). Wires canonical doc, README, AGENTS.md, CLAUDE.md, monitor script in the same pass."
---

# Metric policy wiring (cross-repo default)


When adding/changing any metric definition (zero-touch, smoothness, merge-gate rates, etc.), do not leave it in a one-off doc.

Required same-pass wiring across the target repo:
1. Canonical metric doc (definition + formula)
2. README pointer to canonical doc
3. AGENTS.md and CLAUDE.md policy pointers
4. The monitor/reporting script that computes the metric

If the user asks for cross-repo application, repeat this pattern in each affected repo.

- Prefer concise, direct responses focused on actionable outcomes.
- Make the smallest safe change that solves the request.
- Preserve existing user changes; do not revert unrelated work.
