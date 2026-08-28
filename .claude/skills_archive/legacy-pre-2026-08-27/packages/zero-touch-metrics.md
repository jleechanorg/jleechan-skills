name: zero-touch-metrics
description: Measure zero-touch and one-touch rates from merged PRs — run in evolve loop cycles

---

## Purpose

Measure autonomy metrics for the evolve loop. Run via `/eloop` or standalone.

## Metrics

### Zero-touch
- First commit author != "$USER" (agent-proposed)
- Merged by github-actions[bot]
- No CR CHANGES_REQUESTED ever

### One-touch
- First commit author == "$USER" (human-proposed via /claw)  
- Merged by github-actions[bot]
- No CR CHANGES_REQUESTED ever

### External
- Not agent or $USER authored

## Command

```bash
# Run in agent-orchestrator repo
cd $HOME/project_agento/agent-orchestrator

echo "=== Touch Rate (last N PRs) ==="
for pr in $(gh api 'repos/jleechanorg/agent-orchestrator/pulls?state=closed&per_page=30' --jq '.[] | select(.merged_at != null) | .number' 2>/dev/null | head -25); do
  author=$(gh api "repos/jleechanorg/agent-orchestrator/pulls/$pr/commits" --jq '.[0].commit.author.name' 2>/dev/null)
  echo "$pr|$author"
done
```

## Output format

```
PRIMARY (One-touch rate): X/Y = Z%
SECONDARY (Zero-touch rate): A/B = C%
```