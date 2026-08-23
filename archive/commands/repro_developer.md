---
description: Build a developer reproduction bundle for agent-review failures, missed-plan retrospectives, Claude/Codex transcript comparisons, or cases where Anthropic/OpenAI engineers need raw conversation JSONL, subagent state, repo evidence, hashes, and a concise replay guide.
type: skill
execution_mode: immediate
---

# /repro_developer [args]

Build a developer reproduction bundle with raw agent transcripts and repo evidence, for cases where an Anthropic/OpenAI engineer needs a faithful replay of a Claude/Codex failure.

Read `~/.claude/skills/repro-developer/SKILL.md` and execute the full workflow with the provided args.

## Notes

| Case | Action |
|------|--------|
| July 6-7, 2026 Claude/fable vs Codex plan-miss incident | Use committed LFS artifact `artifacts/repro-developer/claude-fable-adversarial-review-codex-plan-miss/` unless a fresh collection is explicitly requested |
| Fresh collection | Run `.claude/skills/repro-developer/scripts/collect_repro.py --sanitize --require-gitleaks-clean --encrypt-raw --publish-dir ...`, verify LFS pointers with `git lfs status`, never commit the raw passphrase |
