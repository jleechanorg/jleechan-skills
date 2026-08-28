# autor-n15-loop — Phase 3 n=15 per technique loop

**Loop interval**: 30m | **Max duration**: 12h (24 iterations)

## Purpose
Drive SelfRefine/ET/PRM autor PR generation until each technique reaches n=15 samples in the Thompson bandit.

## Entry conditions (all must be true to continue)
- Branch `chore/auto-research-phase3` is pushed and not detached
- No merge conflicts on the branch
- CI is not stuck (>30min queue with no progress)

## Each iteration

### 1. Check bandit state
```
python technique_bandit/technique_selector.py --rank
```
If all three techniques have n≥15 → STOP (goal reached).

### 2. Thompson-suggest next technique
```
python technique_bandit/technique_selector.py --suggest <PR#>
```
Use the suggested technique for the next run.

### 3. Generate autor PR for under-sampled papers
cd to ~/llm-wiki-autor-phase3 (NOT the main workspace).

For the suggested technique, pick a paper from the autor benchmark that has the fewest SelfRefine/ET/PRM samples. Run the autor pipeline:
```
# Example for SelfRefine
cd ~/llm-wiki-autor-phase3
autor run --technique SelfRefine --paper <paper_id> --pr-number <next_pr>
```

If the autor CLI is not available, use the manual workflow:
- Fork/clone the target repo
- Apply the technique (SelfRefine prompt, ET extended thinking, or PRM reasoning)
- Create a draft PR against the original

### 4. Score the new PR
Use the 6-dim rubric on the new PR diff:
```
python layer/score_pr.py <pr_number>
```

### 5. Update bandit
```
python technique_bandit/technique_selector.py --update --PR <pr> --score <score> --technique <tech>
```

### 6. Close the PR (evaluation artifact, never merge)
```
gh pr close <pr> --repo $GITHUB_REPOSITORY \
  --comment "autor eval: $tech score=$score. Closing — evaluation artifact, not a merge candidate."
```
Autor PRs are **evaluation artifacts**, not merge candidates. Always open as draft, always close after scoring. Do not leave them open.

### 7. Commit + push
```
git add -A && git commit -m "autor: <tech> n=$(n+1) score=<score>" && git push
```

### 8. Check time budget
If elapsed > 12h since first iteration → STOP.

## Stop conditions
- All three techniques reach n≥15 → SUCCESS
- 12 hours elapsed → PARTIAL (note final n for each technique)
- Error on 3 consecutive iterations → FAIL (notify)

## Priority order when choosing papers
1. Papers with NO samples yet for any technique
2. Papers with samples for only 1-2 techniques (fill gaps)
3. Papers with lowest combined score across techniques

## Output
After each iteration, print:
```
[iter N] SelfRefine n=X | ET n=Y | PRM n=Z | elapsed=Thh:mm
```
