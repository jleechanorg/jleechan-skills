---
name: credential-discipline
description: Example/seed/fixture files must use placeholders not real credentials. Pre-commit grep check + enforcement hooks.
---

## Rule: examples, seeds, and test fixtures must use placeholders, not real values.

### What counts as an example

Any file under: `examples/`, `seed/`, `seed_data/`, `test_data/`, `fixtures/`, `mocks/`
Or filename contains: `example`, `seed`, `fixture`, `mock`, or `sample`

### Required placeholder scheme

| Real value | Placeholder |
|---|---|
| `AIzaSy...` (Firebase / Google API key) | `<your-firebase-api-key>` |
| Record or document ID (e.g. a campaign ID) | `<your-record-id>` |
| Auth user UID | `<your-firebase-uid>` |
| Real person's email (test account) | `<your-test-user>@example.com` |
| GCP / Firebase project ID or number | `<your-firebase-project-id>` |
| Any other identifier | `<your-<descriptor>>` |

### Machine-local blocklist

Never write the real values you must not paste into a skill, test, or commit.
Keep them, one fixed string per line, in a machine-local file that is never
committed: `$CREDENTIAL_BLOCKLIST_FILE`, default
`${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/credential-blocklist.txt`.
Typical entries are your own project IDs, project numbers, test-account UIDs,
record IDs from production data, and personal email addresses.

### Before-commit checklist

```bash
BLOCKLIST="${CREDENTIAL_BLOCKLIST_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/credential-blocklist.txt}"
grep -rnE 'AIza[A-Za-z0-9_-]{35}' examples/ 2>&1
if [ -s "$BLOCKLIST" ]; then
  grep -rnF -f "$BLOCKLIST" examples/ 2>&1
else
  echo "CREDENTIAL_BLOCKLIST_FILE not configured: file of real identifiers to block, one per line. Example: export CREDENTIAL_BLOCKLIST_FILE=$HOME/.config/jleechan-skills/credential-blocklist.txt" >&2
fi
```

Any match is a leak to replace with a placeholder before committing.

### Enforcement

- **Pre-commit hook:** `~/.claude/hooks/pre-commit-git-identity-example-com-guard.sh` blocks commits by `@example.com`.
- **Per-repo test:** `tests/test_example_placeholder_discipline.sh` in CI for each repository that ships examples.
- **Per-repo hook:** `.githooks/pre-commit` chains identity guard + discipline test on staged `examples/**`.

### Why

3 real production credential leaks landed in public repos between 2026-02 and 2026-04. `.gitleaksignore` is suppression, not a fix — rotate keys + rewrite history.

**If example needs real credential:** move to private repo, parameterize via env var, or use Firebase Emulator.
