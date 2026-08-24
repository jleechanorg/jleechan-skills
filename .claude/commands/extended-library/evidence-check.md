# /evidence-check — Validate PR body against Evidence Gate locally

Run this before pushing a PR to catch Evidence Gate failures locally instead of waiting for CI.

## Usage

```
/evidence-check [--pr N]
```

- `--pr N`: PR number to check. If omitted, detects from current branch via `gh pr status`.

## What it checks

The Evidence Gate CI check (`wholesome.yml` "Evidence Has Media Attachment") has three hard requirements:

1. **Evidence section present** — PR body must contain `## Evidence` (H2 heading)
2. **Claim class** — Must have `**Claim class**: <unit|integration|pipeline-e2e|pr-lifecycle-e2e|merge-gate>`
3. **Media proof** — Evidence section must contain EITHER:
   - Markdown image with HTTPS URL: `![alt](https://...)`
   - OR a code block: `\`\`\``
   - OR structured text: `**Terminal output**:` or `**Test output**:` followed by non-whitespace

**What FAILS the CI check:**
- `**Media**: <path>` — placeholder path without actual image URL
- `**Test output**: <value>` — inline value without code block or URL
- No Evidence section at all

## Script (run locally)

```bash
#!/bin/bash
set -euo pipefail

PR_NUM="${1:-}"
if [ -z "$PR_NUM" ]; then
  PR_NUM=$(gh pr status --json number --jq '.current.number // empty')
fi

BODY=$(gh api repos/jleechanorg/agent-orchestrator/pulls/"$PR_NUM" --jq '.body')

echo "=== Evidence Gate Local Check ==="
echo "PR #$PR_NUM"
echo ""

FAIL=0

# Check 1: Evidence section
if printf '%s' "$BODY" | grep -qiE '^[[:space:]]*##[[:space:]]+[Ee]vidence([[:space:]]|$)'; then
  echo "✓ Evidence section found"
else
  echo "✗ MISSING: No ## Evidence section found"
  FAIL=1
fi

# Check 2: Claim class
CLAIM=$(printf '%s' "$BODY" | grep -i '\*\*Claim class' | grep -v '^- ' | head -1 | sed 's/.*\*\*Claim class\*\*: *//I' | sed 's/(.*//' | tr -d '*' | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/^[ \t-]*//;s/[ \t-]*$//')
if [ -n "$CLAIM" ]; then
  echo "✓ Claim class: $CLAIM"
else
  echo "✗ MISSING: No **Claim class** found"
  FAIL=1
fi

# Check 3: Media proof (within Evidence section only)
EVIDENCE=$(printf '%s\n' "$BODY" | awk '
  BEGIN { IGNORECASE=1 }
  /^[[:space:]]*##[[:space:]]+[Ee]vidence([[:space:]]|$)/ { in_section=1; next }
  in_section && /^[[:space:]]*##[[:space:]]/ { exit }
  in_section { print }
')
if [ -n "$EVIDENCE" ]; then
  if printf '%s' "$EVIDENCE" | grep -qiE '!\[[^]]*\]\(https://[^)]+\)'; then
    echo "✓ Media: markdown image with HTTPS URL"
  elif printf '%s' "$EVIDENCE" | grep -q '```'; then
    echo "✓ Media: code block found"
  elif printf '%s' "$EVIDENCE" | grep -qiE '\*\*(Test|Terminal) output\*\*:[[:space:]]+\S'; then
    echo "✓ Media: structured terminal/test output"
  else
    echo "✗ MISSING: No media found in Evidence section"
    echo "  Expected: ![alt](https://...) OR \`\`\`...\`\`\` OR **Terminal output**: <value>"
    FAIL=1
  fi
fi

echo ""
if [ $FAIL -eq 0 ]; then
  echo "PASS: PR body will pass Evidence Gate CI"
  exit 0
else
  echo "FAIL: Fix Evidence Gate issues before pushing"
  exit 1
fi
```

## Exit codes

- `0`: PR body passes all Evidence Gate checks
- `1`: One or more checks fail — fix before pushing
