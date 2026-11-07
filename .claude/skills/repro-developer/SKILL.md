---
name: repro-developer
description: Build a developer reproduction bundle for agent-review failures, missed-plan retrospectives, Claude/Codex transcript comparisons, or cases where Anthropic/OpenAI engineers need raw conversation JSONL, subagent state, repo evidence, hashes, and a concise replay guide.
---

# Repro Developer

Use this skill when a user wants a reproducible artifact bundle for an agent failure or cross-agent comparison, especially when raw Claude/Codex conversations, subagent transcripts, repo commits, and local state are needed.

## Workflow

1. Identify the incident and claim.
   - State the exact failure mode in one sentence.
   - Separate raw evidence from interpretation.
   - Prefer full transcript/session files over excerpts.

2. Collect artifacts with `scripts/collect_repro.py`.
   - Include Claude parent sessions and their session directories when present.
   - Include subagent JSONL/meta files and workflow journals.
   - Include Codex parent/subagent sessions that caught or analyzed the miss.
   - Include repo evidence files, bead snapshots, git status/log, and command/skill definitions.
   - Produce hashes and a manifest so a developer can verify integrity.

3. Write a replay guide.
   - Explain chronology: initial workflow, missed issue, later catching workflow, retrospective/fix.
   - Name the concrete files to inspect first.
   - Include exact local paths and, when available, GitHub commit URLs.
   - Mark any missing/private artifacts honestly.

4. Package, do not commit large raw transcripts to an ordinary repo by default.
   - Default output belongs under `/tmp/repro-developer-*`.
   - If long-term sharing is needed in git, publish only gitleaks-clean sanitized archives and encrypted raw archives through Git LFS.
   - Do not paste large transcript contents into prompts or PR bodies.

5. Check for sensitive material before sharing externally.
   - Do not delete raw files from the bundle, but add `SENSITIVE_REVIEW.md` with findings.
   - Flag credentials, private repo names, personal email, and tokens.
   - For holdout/evaluator content, include path and hash metadata only unless the user explicitly authorizes sharing the sealed material.
   - Treat `gitleaks detect --no-git` on the sanitized bundle as the required pass/fail gate.

6. For git-native handoff, produce two LFS artifacts.
   - Sanitized archive: redacted, gitleaks-clean, suitable for normal repo access.
   - Exact raw archive: encrypted `.gpg` file, suitable for Git LFS transport only; passphrase stays out of git and is shared out of band.
   - Never commit the raw plaintext archive or the passphrase file.

## Commands

Paths may use `$VARS` and `~`; the script expands them. Session stores default to
`${CLAUDE_HOME:-$HOME/.claude}` and `${CODEX_HOME:-$HOME/.codex}`; the script applies those
defaults itself when the variable is unset or empty, for both command-line values and
profile files. Explicit values still win. `--repo` defaults to the current directory.

Create a bundle (replace every `<...>` placeholder with the incident's real paths):

```bash
python3 "${CLAUDE_HOME:-$HOME/.claude}"/skills/repro-developer/scripts/collect_repro.py \
  --repo "$(git rev-parse --show-toplevel)" \
  --incident <incident-slug> \
  --out /tmp \
  --claim "<one-sentence failure claim>" \
  --claude-session "${CLAUDE_HOME:-$HOME/.claude}/projects/<project-slug>/<session-id>.jsonl" \
  --claude-session-dir "${CLAUDE_HOME:-$HOME/.claude}/projects/<project-slug>/<session-id>" \
  --codex-session /path/to/codex-parent.jsonl \
  --codex-session /path/to/codex-subagent.jsonl \
  --repo-file docs/<review-doc>.md \
  --repo-file docs/<retrospective-doc>.md \
  --bead <bead-id>
```

Create git/LFS-ready artifacts by adding `--sanitize`,
`--require-gitleaks-clean`, `--encrypt-raw`, and
`--publish-dir artifacts/repro-developer/<incident-slug>` to the complete
`collect_repro.py` command above.

```bash
git lfs track "artifacts/repro-developer/**"
git add .gitattributes artifacts/repro-developer/<incident-slug>
```

To rerun a recorded incident, keep its inputs in a profile JSON file and pass
`--incident-profile <file>`. Keys: `incident`, `claim`, `incident_commit`,
`artifact_commit`, and lists `claude_sessions`, `claude_session_dirs`,
`codex_sessions`, `repo_files`, `beads`. An explicit non-empty flag list replaces the
corresponding profile list; the other profile lists still apply. A profile does not turn on
`--include-dirty-diff`, `--include-beads-jsonl`, `--write-env-report`, or `--verify`; pass
those capture flags explicitly.

```json
{
  "incident": "<incident-slug>",
  "claim": "<one-sentence failure claim>",
  "claude_sessions": ["$CLAUDE_HOME/projects/<encoded-repo-path>/<session-uuid>.jsonl"],
  "codex_sessions": ["$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<id>.jsonl"],
  "repo_files": ["docs/<review-doc>.md"],
  "beads": ["<bead-id>"]
}
```

The sanitizer redacts the literal sealed-holdout tokens and, when
`DARK_FACTORY_HOLDOUTS` is set, that checkout's path.

The script writes:

- `manifest.json` with source paths, sizes, hashes, git metadata, and generated files.
- `REPLAY.md` with a developer-oriented reading order.
- `raw/claude/` and `raw/codex/` with transcripts and subagent state.
- `repo/` with selected source documents and command outputs.
- `checksums.sha256`.
- `<incident>.tar.zst` when `zstd` exists, otherwise `<incident>.tar.gz`.
- With `--sanitize`, a sibling sanitized bundle plus `<incident>-sanitized.tar.*`.
- With `--encrypt-raw`, an encrypted raw archive and a local passphrase file that must not be committed.

## Quality Bar

A bundle is complete only if it contains:

- The initial agent workflow that produced the missed plan or claim.
- The later review that caught the issue.
- Raw subagent state, not just summaries.
- The repo artifacts that show the missed facts were already present.
- A manifest with hashes for every copied file.
- A replay guide that can be followed without needing this chat.
- For git handoff: a sanitized archive that passes gitleaks and an encrypted exact archive whose passphrase is not in git.

If any of those are unavailable, mark the bundle `PARTIAL` in `REPLAY.md` and list the missing evidence.
