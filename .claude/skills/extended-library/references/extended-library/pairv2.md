---
description: Launch LangGraph-based pair programming v2 with left/right contract gating
argument-hint: '"task description"'
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
When this command is invoked, execute the script below directly.

Install dev dependencies first (once per workspace):

```bash
./vpython -m pip install -r .claude/scripts/requirements-dev.txt
```

```bash
python3 .claude/pair/pair_execute_v2.py \
  --left-contract path/to/left_contract.json \
  --right-contract path/to/right_contract.json \
  "$ARGUMENTS"
```

Live mode (real coder/verifier agents) example:

```bash
python3 .claude/pair/pair_execute_v2.py \
  --coder-cli claude \
  --verifier-cli codex \
  --left-contract path/to/left_contract.json \
  --right-contract path/to/right_contract.json \
  "$ARGUMENTS"
```

## Purpose

`/pairv2` is the LangGraph state-machine executor for contract-gated pair programming.

The verifier agent is the **spec adherence enforcer** — it checks both directions:

**Left contract adherence** (spec → implementation):
Every requirement stated in the left contract must be traceable to actual code.
The verifier finds the function/file for each requirement and flags gaps.

**Right contract adherence** (implementation → documentation):
Every factual claim in docs/roadmaps must match file system reality:
- Line counts verified with `wc -l`
- Status headers ("COMPLETE") must be consistent with checklist items
- Test counts must be re-run, not trusted from prior claims
- `[ ]` items must each carry an explicit DEFERRED reason

The three graph nodes that enforce this:
1. `_left_contract_node` — gates entry: task spec must be unambiguous
2. `_implement_node` (coder) → `_verify_right_contract_node` (verifier) — iterative loop
3. `_finalize_node` — records verdict only after verifier confirms both contracts

It outputs a structured verdict artifact at:
`benchmark_results/pairv2_latest/pairv2_result.json`
