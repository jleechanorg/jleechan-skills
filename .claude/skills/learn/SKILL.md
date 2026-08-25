---
name: learn
description: Capture durable learnings from failures, corrections, repeated mistakes, successful recovery patterns, or direct /learn requests. Use whenever the user invokes /learn, asks to save/remember/capture a lesson, or when a workflow failure should become reusable process knowledge. Always persist to Claude memory, optional mem0, ~/roadmap, beads, and wiki-ingest.
---

# Learn

Use this skill to turn a concrete lesson into durable, discoverable artifacts. Do
not stop at a chat summary. A complete learning capture writes the file-backed
records that future agents and reviewers will actually find.

## Required outputs

Every confirmed learning must produce or update all of these:

1. Claude auto-memory under `~/.claude/projects/<project-key>/memory/`.
2. Optional mem0 save when the configured helper and API key are available.
3. Monthly roadmap log at `~/roadmap/learnings-YYYY-MM.md`.
4. A closed or referenced bead in `.beads/issues.jsonl` when the current repo has beads.
5. LLM wiki ingest under `~/llm_wiki`: raw source copy, source page, index entry, log entry, and relevant concept/entity updates.

If a persistence target is unavailable, report the exact blocker and continue
with the remaining targets. Do not silently skip wiki ingest.

## Workflow

### 1. Extract the learning

- If the user supplied a lesson, use it as the source.
- If the user invoked `/learn` without specifics, inspect the recent
  conversation and extract the most actionable failure, correction, or pattern.
- Classify it as `Critical`, `Mandatory`, `Best Practice`, or `Anti-Pattern`.
- Prefer precise references: PR URLs, commit SHAs, file paths, commands, error
  strings, artifacts, and verification results.
- Search existing local records before writing:
  - `~/.claude/projects/**/memory`
  - `~/roadmap/learnings-*.md`
  - `.beads/issues.jsonl`
  - `~/llm_wiki/wiki/index.md` and relevant `concepts/` pages

### 1a. Fix vs. Document decision (apply BEFORE writing the memory entry)

Workarounds-as-memory are NOT a complete resolution when a small fix is possible. Apply the fix-on-discovery rule from `~/.claude/CLAUDE.md`:

| Bug class | Action |
|---|---|
| User-managed config (yaml/plist/dotfile) + fix < 10 lines + currently blocking | **FIX IT NOW**, then write memory entry that *references the fix* (commit SHA, diff, or `~/.hermes/...:line`). Memory body must say "FIX: <what> at <where> on <date>" — not just "workaround: ..." |
| User's published code in a separate PR scope (separate repo, separate concern) | Document workaround; open a dedicated fix PR; memory links the fix PR |
| Third-party code (provider outage, npm package, OS-level) | Workaround only — no fix possible from here. Memory describes the trigger conditions and the recovery path |
| Agent-orchestrator core code in same repo | Fix in same PR per project CLAUDE.md; memory captures the *pattern* (e.g. "configKey/name/path mismatch must be validated at write-time") so the fix is durable |
| Documentation, test, tooling, scripts | Document; no fix required |

If you find yourself writing "workaround: ..." without a corresponding fix, re-read the table. The most common mistake is treating a 1-line config fix as "out of scope" — that is exactly the class this rule targets.

### 2. Write Claude auto-memory

**Determine memory type from classification**: Critical/Mandatory rules → `feedback`;
architecture or design decisions → `project`; best practices → `feedback`; durable
external facts or documentation-style lookups → `reference`.

Use the current git root to derive the project memory path:

```text
project_key = git_root.replace("/", "-")
memory_dir = ~/.claude/projects/<project_key>/memory/
```

Create or update:

- `<type>_YYYY-MM-DD_<slug>.md`
- `MEMORY.md`

**Never let a write failure (permissions, disk) block learning capture.** If the
write fails, log a warning and continue to the remaining persistence targets.

The memory file must include frontmatter:

```yaml
---
name: <learning title>
description: <one-line summary>
type: feedback|project|reference
bead: <bead id or none>
---
```

The body must include context, technical detail, solution or rule, verification,
references, and a reusable pattern.

### 3. Save to mem0 when available

Save a concise text record only when a configured helper and the **mem0 Python
package** are present. **Do NOT probe `OPENAI_API_KEY` / `MEM0_API_KEY`** — those
were the pre-Ollama-era gates; mem0 now uses local Ollama embedder + Groq LLM
(configured in `~/.hermes/.claude/hooks/mem0_config.py`), neither of which
require `OPENAI_API_KEY`. The real availability gates are:

1. `python3 -c "from mem0 import Memory"` resolves (requires `mem0ai` PyPI pkg).
2. The helper script exists:
   - `~/.hermes/.claude/hooks/mem0_save.py` (Hermes state dir — used on this machine), OR
   - `$(git rev-parse --show-toplevel)/.claude/hooks/mem0_save.py` (repo-local fallback)
3. `~/.hermes/.claude/hooks/mem0_config.py:mem0_hooks_enabled()` returns `True`
   (this is the helper's own gate — it inspects `OPENAI_API_KEY`, `GROQ_API_KEY`,
   `OLLAMA_HOST`, etc., not what we hard-code here).

**Verification step (mandatory before reporting "mem0 unavailable"):** Run the
existing read-only health check. Do not manufacture a learning message or require a
Qdrant/markdown write merely to test availability:

```bash
~/.hermes/.venv/bin/python3 -c '
import importlib.util
from pathlib import Path
assert importlib.util.find_spec("mem0")
assert Path.home().joinpath(".hermes/.claude/hooks/mem0_save.py").is_file()
'
```

Only if this fails (or the helper/import probe fails) report `mem0 unavailable:
<exact blocker>`. Otherwise report `mem0 available` and save only the actual learning.
**Never block learning capture on a mem0 error** — it is an optional target;
continue to the remaining persistence steps regardless of outcome.

Reference incident: 2026-06-24 — old SKILL.md probed `OPENAI_API_KEY` and
falsely reported "mem0 unavailable" for ~2 months after the Ollama/Groq switch
in PR #7178 / bead `rev-1cmaj` (2026-05-24).

### 4. Append `~/roadmap` learning log

Append to `~/roadmap/learnings-YYYY-MM.md`:

```markdown
## YYYY-MM-DD - <learning title>

- **Type**: feedback|project|reference
- **Classification**: Critical|Mandatory|Best Practice|Anti-Pattern
- **Summary**: <one-line summary>
- **Bead**: <bead id or none>
- **Files**: <paths created or updated>
- **References**: <PRs, commits, artifact links, commands>
```

### 5. Create or reference a bead

If `.beads/issues.jsonl` exists:

- Reuse a matching learning bead when one already exists.
- Otherwise create a closed task bead with labels including `learning` and
  `documentation`.
- Use the repository's normal bead id prefix when possible. In your-project.com,
  prefer `br create ... --type task --priority 3` or the existing `rev-` prefix
  rather than inventing a `bd-` id.
- Record the bead id in the Claude memory frontmatter and roadmap entry.

If beads are unavailable, write `none` and report why.

### 6. Always wiki-ingest (call the skill, do not write files manually)

Wiki ingest is mandatory for `/learn`. Use the Claude memory file (preferred)
or the roadmap entry as the source document. **Invoke the `wiki-ingest`
skill via the Skill tool — do not write files into `~/llm_wiki/wiki/`
directly.** The `wiki-ingest` skill handles raw copy, source page, index
entry, log entry, and entity/concept extraction in one call.

```
Skill("wiki-ingest", args="<absolute path to memory file or roadmap entry>")
```

After invoking, verify all four side effects landed:

- `~/llm_wiki/raw/<basename>` exists
- `~/llm_wiki/wiki/sources/<slug>.md` exists with the canonical frontmatter
  (`title`, `type`, `tags`, `sources`, `last_updated`) and `[[wikilinks]]`
- `~/llm_wiki/wiki/index.md` was updated under `## Sources`
- `~/llm_wiki/wiki/log.md` was appended with `## [YYYY-MM-DD] ingest | <title>`

**Do NOT fall back to direct `Write` / `Edit` / `cp` / `python3 <<EOF`**
when the skill fails. The global wiki integrity rule forbids direct
writes to `wiki/sources/`, `wiki/entities/`, and `wiki/concepts/`, and
direct writes skip the entity/concept extraction that the skill performs.
If the skill errors, surface the error to the user and stop — never
silently substitute a partial manual write.

**No exceptions for "the learning seems not wiki-bearing."** The learning
itself is the source. The skill's classifier decides what is wiki-bearing.

**Working-directory caveat**: if the current session cwd is not
`~/llm_wiki` (e.g. an `/integrate` flow running in a feature worktree),
`Skill("wiki-ingest", args="<abs path to memory file>")` still works
because it accepts an absolute path and resolves `WIKI_ROOT` from
`$HOME/llm_wiki` by default. Do not `cd ~/llm_wiki` first; pass the
absolute path in `args`.

### 7. Validate and report

Before reporting complete:

- Verify files exist for each persistence target that was available.
- Validate `.beads/issues.jsonl` parses when modified.
- Check duplicate bead ids when a bead was created manually.
- Run a whitespace check for repo changes when applicable.

Final report must name the created/updated paths and any skipped persistence
target with its reason.
