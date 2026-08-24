---
description: Save evidence to /tmp structure
type: skill
execution_mode: immediate
---

# /savetmp <work_name> [--flags]

Archive evidence to a structured `/tmp` layout following evidence standards.

Read `~/.claude/skills/evidence-standards/SKILL.md` for the full evidence methodology, then execute `.claude/commands/savetmp.py` to archive evidence.

**Features:**
- SHA256 checksums for all evidence files (evidence integrity)
- Git provenance capture (HEAD commit, origin/main, changed files)
- Parallel git command execution for speed
- Structured `/tmp/<repo>/<branch>/<work>/<timestamp>/` layout
- Metadata paths stored as relative paths for portability
- Optional validation pass for checksum gaps and portability issues

## Quick Usage

```bash
python .claude/commands/savetmp.py "<work_name>" \
  --methodology "<testing approach>" \
  --evidence "<results summary>" \
  --notes "<follow-up notes>" \
  --artifact <path/to/file-or-directory>
```

## Flags

| Flag | Purpose |
| ---- | ------- |
| `--methodology` / `--methodology-file` | Testing methodology |
| `--evidence` / `--evidence-file` | Evidence summary |
| `--notes` / `--notes-file` | Additional notes |
| `--artifact` | Copy file/dir to artifacts/ (repeatable) |
| `--command-log` | Copy a test run log that includes command + stdout/stderr + exit code |
| `--capture-git-provenance-full` | Write `git_provenance_full.txt` with raw git command output + exit codes |
| `--skip-git` | Skip git commands for faster execution |
| `--clean-checksums` | Remove existing `.sha256` files from artifacts before packaging |
| `--validate` | Run post-package validation (checksums, portability, required files) |
| `--llm-claims` | Declare LLM/API behavior claims (requires `request_responses.jsonl`) |

## Output Structure

```
/tmp/<repo>/<branch>/<work>/<timestamp>/
├── methodology.md + .sha256
├── evidence.md + .sha256
├── notes.md + .sha256
├── metadata.json + .sha256   # Includes provenance + checksum_mode
├── README.md + .sha256
├── git_provenance_full.txt + .sha256   # Optional, with --capture-git-provenance-full
└── artifacts/
```

## Evidence Standards Reference

See `~/.claude/skills/evidence-standards/SKILL.md` for:
- Three Evidence Rule (Configuration, Trigger, Log)
- Mock vs Real mode decision tree
- Git provenance requirements
- Checksum verification
- Test execution evidence requirements (command + output + exit code)
