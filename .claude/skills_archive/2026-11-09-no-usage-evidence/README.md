# No-Usage-Evidence Skills Archive — 2026-11-09

Skills moved out of the installed set because a usage review found no evidence of use: no explicit skill call, file open or typed `/name` in Claude Code history; no skill-file open by a Codex tool call on either host in 14 days; no mention in an always-loaded instruction file; not created in November 2026.

Full classification of the 308 reviewed names, and the one in-repo skill that was held back because an active skill still depends on it, is in `docs/skill-archive-2026-11-09.md`.

## Archival Inventory

| Skill | Former Path |
|---|---|
| `blogwatcher` | `.claude/skills/blogwatcher/` |
| `chroma` | `.claude/skills/chroma/` |
| `clip` | `.claude/skills/clip/` |
| `codebase-inspection` | `.claude/skills/codebase-inspection/` |
| `coderabbit` | `.claude/skills/coderabbit/` |
| `docx` | `.claude/skills/docx/` |
| `faiss` | `.claude/skills/faiss/` |
| `goalexec-define` | `.claude/skills/goalexec-define/` |
| `hermes-models` | `.claude/skills/hermes-models/` |
| `karpathy-wiki` | `.claude/skills/karpathy-wiki/` |
| `llava` | `.claude/skills/llava/` |
| `mcp-builder` | `.claude/skills/mcp-builder/` |
| `mem0` | `.claude/skills/mem0/` |
| `minecraft-modpack-server` | `.claude/skills/minecraft-modpack-server/` |
| `nemo-curator` | `.claude/skills/nemo-curator/` |
| `orchconverge` | `.claude/skills/orchconverge/` |
| `pair-benchmark-all-executors` | `.claude/skills/pair-benchmark-all-executors/` |
| `pptx` | `.claude/skills/pptx/` |
| `pr-description-format` | `.claude/skills/pr-description-format/` |
| `pr-report` | `.claude/skills/pr-report/` |
| `webapp-testing` | `.claude/skills/webapp-testing/` |
| `whisper` | `.claude/skills/whisper/` |
| `xlsx` | `.claude/skills/xlsx/` |

## Recoverability

Restore one skill with `git mv .claude/skills_archive/2026-11-09-no-usage-evidence/<name> .claude/skills/<name>`, then revert the matching reference edit listed in `docs/skill-archive-2026-11-09.md` if there is one. `coderabbit`, `goalexec-define` and `pr-report` were archived together with the commands that dispatched to them; see `.claude/commands_archive/2026-11-10-no-usage-evidence/README.md`.
