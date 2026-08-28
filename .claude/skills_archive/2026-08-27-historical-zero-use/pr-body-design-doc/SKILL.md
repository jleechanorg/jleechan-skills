---
name: pr-body-design-doc
description: "Use for production-code PRs ($PROJECT_ROOT/**, gates, ZFC). Requires full GitHub URL to governing roadmap/design doc and a `br` bead ID in the body."
---

# PR body — governing design doc and bead (prod / gates / ZFC)


For any PR that changes production code under `$PROJECT_ROOT/**`, CI gates, or ZFC/level-up behavior, the PR description **must** include:

1. A **full GitHub blob URL** to the governing `roadmap/*.md` or `docs/design/**` file on `$GITHUB_REPOSITORY`, or the literal **`N/A`** with a one-line justification (docs-only typos, etc.).
2. A **`br` bead ID** (e.g. `rev-xxxxx`) or **`N/A`** with justification.

Level-up or `rewards_engine` / `world_logic` work must also cite the canonical design + task-spec links:

- [roadmap/zfc-level-up-model-computes-2026-04-19.md](https://github.com/$GITHUB_REPOSITORY/blob/main/roadmap/zfc-level-up-model-computes-2026-04-19.md)
- [roadmap/zfc-pr-task-specs-2026-04-22.md](https://github.com/$GITHUB_REPOSITORY/blob/main/roadmap/zfc-pr-task-specs-2026-04-22.md)

Repo default template: `your-project.com` → `.github/pull_request_template.md`. **CI does not parse PR bodies** for these links; `design-doc-gate.yml` enforces code grep gates only—human and agent discipline fills the gap.
