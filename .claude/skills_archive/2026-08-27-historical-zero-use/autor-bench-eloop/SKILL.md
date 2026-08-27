# autor-bench-eloop — Autor Research + SWE-bench Benchmark Loop

**Loop interval**: 30m | **Max duration**: 12h (24 iterations)

## Purpose

Drive the autor research + benchmarking pipeline: run `run_autor_experiment.py` for technique comparison, evaluate against SWE-bench, and build the bandit state for technique selection.

## Entry conditions (all must be true to continue)
- `run_autor_experiment.py` exists and passes `python3 -m py_compile`
- SWE-bench cloned at `~/.swes/`
- `ai_orch` accessible at `~/worktrees/pr6270-swebench/orchestration/`
- No active background runs (check `tmux list-sessions` for `autor-*` sessions)
- Bandit state at `technique_bandit/bandit_state.json` readable

## Each iteration

### Phase 1: OBSERVE — System State

```bash
# Check active autor runs
tmux list-sessions 2>/dev/null | grep -E "autor-|swebench-" || echo "no active sessions"

# Check latest score files
ls -t research-wiki/scores/SR-*.json 2>/dev/null | head -5

# Check SWE-bench eval status
ls -t ~/.swes/eval_results/ 2>/dev/null | head -3 || echo "no eval results yet"

# Check bandit state
python3 -c "import json; d=json.load(open('technique_bandit/bandit_state.json')); [print(f'{k}: n={v[\"n\"]}, mean={v[\"mean\"]:.2f}') for k,v in d['techniques'].items()]"
```

### Phase 2: MEASURE — Quality Metric

Primary metric: **rubric mean** across techniques in `bandit_state.json`.
Secondary metric: **SWE-bench resolution rate** (instances solved / total evaluated).

```bash
# Compute current technique means
python3 -c "
import json
d = json.load(open('technique_bandit/bandit_state.json'))
for k, v in sorted(d['techniques'].items(), key=lambda x: -x[1].get('mean',0)):
    print(f'{k}: n={v[\"n\"]}, mean={v[\"mean\"]:.2f}')
"

# Check SWE-bench results if available
if [ -f ~/.swes/eval_results/latest.json ]; then
  python3 -c "import json; d=json.load(open('$HOME/.swes/eval_results/latest.json')); print(f'SWE-bench: {d[\"resolved\"]}/{d[\"total\"]} = {d[\"resolved\"]/max(d[\"total\"],1)*100:.1f}%')"
fi
```

### Phase 3: DIAGNOSE — What needs running?

Decision tree:
- **All techniques n≥15 AND SWE-bench eval done** → STOP (goal reached)
- **SR-multi-exemplar or SR-prtype have n<12** → run `run_autor_experiment.py --technique <technique> --prs 6265,6261,6245,6269 --n 1`
- **No SWE-bench comparison done** → run SWE-bench comparison via `swebench-tester` subagent
- **ai_orch CLI comparison not done** → run `ai_orch --agent-cli claude` vs `run_autor_experiment.py` comparison
- **Live run divergence from computed** → flag in findings

### Phase 4: PLAN — Next dispatch

Based on diagnose, pick ONE of:
1. `python scripts/run_autor_experiment.py --technique SR-multi-exemplar --prs 6265,6261,6245,6269 --n 1`
2. `python scripts/run_autor_experiment.py --technique SR-prtype --prs 6265,6261,6245,6269 --n 1`
3. Spawn SWE-bench comparison via `swebench-tester` subagent
4. Spawn ai_orch CLI comparison via `aiorch-cli-tester` subagent

### Phase 5: RECORD — Log findings

Append to `wiki/syntheses/et_logs/eloop_cycles.md`:

```markdown
## YYYY-MM-DD HH:MM cycle

### Quality metric: technique means from bandit_state.json
### SWE-bench: X resolved / Y evaluated
### Live vs computed gap: ±X points
### New runs dispatched: [list]
### Findings: [observations]
```

```bash
touch /tmp/autor_bench_eloop_last_run
```

### Phase 6: FIX — Run experiments

**6a. Run autor experiment:**
```bash
cd $HOME/llm-wiki-autor-phase3
python scripts/run_autor_experiment.py --technique <chosen> --prs 6265,6261,6245,6269 --n 1 --outdir research-wiki/scores
```

**6b. Run SWE-bench comparison if dispatched:**
Use `swebench-tester` subagent — runs predictions through SWE-bench harness.

**6c. Run ai_orch CLI comparison if dispatched:**
Compare raw CLI output (claude/codex/gemini via ai_orch) vs autor harness on same SWE-bench instances.

### Phase 7: RECAP

```
## Autor-Bench Loop Cycle — HH:MM
- Best technique: X @ Y.mean (n=Z)
- Live vs computed: ±X pts
- SWE-bench: X% resolution (N/M)
- Next run: technique=Z
```

---

## Metrics Tracking

| Metric | Source | Healthy threshold |
|--------|--------|-----------------|
| SR-multi-exemplar mean | bandit_state.json | >86 (Phase 7 live target) |
| Live vs computed gap | run output vs phase7_results.md | <3 pts |
| SWE-bench resolution | ~/.swes/eval_results/latest.json | >15% (beats SWE-agent) |

---

## Anti-Stall Rules

- If run_autor_experiment.py fails → log error, skip to next technique
- If SWE-bench harness fails → log, skip to CLI comparison
- If all techniques at n≥15 → STOP, write final synthesis
- If tmux session stuck (>1h) → kill session, restart run
- If bandwidth limited → prioritize SR-multi-exemplar (current best)

## Invocation

```bash
# Start the loop (via /loop skill)
/loop 30m /autor-bench-eloop

# Or manually for one cycle
/autor-bench-eloop
```

## Key Files

- `scripts/run_autor_experiment.py` — deterministic autor harness
- `technique_bandit/bandit_state.json` — bandit state + technique scores
- `research-wiki/scores/SR-*.json` — score artifacts
- `wiki/syntheses/phase7_results.md` — Phase 7 synthesis
- `~/.swes/` — SWE-bench evaluation suite
- `~/worktrees/pr6270-swebench/orchestration/` — ai_orch CLI orchestration