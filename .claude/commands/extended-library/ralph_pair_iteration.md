---
description: ralph_pair_iteration
type: llm-orchestration
execution_mode: llm-driven
---

# Ralph-Pair Iteration Command

This command runs ONE iteration of Ralph-Pair against the Amazon Clone benchmark.

## Context

- **Workspace**: `ralph/benchmarks/`
- **PRD**: `amazon_clone_prd.json`
- **Spec**: `amazon_clone_full_design_contract.md`
- **Mode**: Coder + Verifier (runs verifyCommand after each iteration)

## Ralph-Pair Flow

### Phase 1: Coder Phase

Same as regular Ralph - implement the Amazon clone:

1. Read PRD and spec
2. Generate complete e-commerce application
3. Create all required files
4. Run tests

### Phase 2: Verifier Phase

After coder completes, run verification:

1. Check all expected files exist
2. Run `python3 -m pytest -q`
3. Verify `evidence/amazon_clone_flow.webm` exists (captioned video)
4. Auto-mark stories as passed if verification succeeds

## Required Files

- `app.py` - Main Flask/Python application
- `in_memory_db.py` - Database layer
- `templates/index.html` - Product catalog page
- `templates/cart.html` - Shopping cart
- `templates/checkout.html` - Checkout flow
- `templates/order_confirmation.html` - Order confirmation
- `static/styles.css` - Styling
- `tests/test_app.py` - Tests
- `evidence/shadow_validation.txt` - Validation output
- `evidence/final_order_confirmation.png` - Screenshot proof
- `evidence/amazon_clone_flow.webm` - **Captioned video (KEY ARTIFACT)**

## Verification Command

```bash
# Check files
ls -la evidence/

# Run tests
python3 -m pytest -q
```

## Success Criteria

1. All expected files exist
2. `python3 -m pytest -q` passes (exit code 0)
3. `evidence/amazon_clone_flow.webm` exists (captioned video)
4. `evidence/final_order_confirmation.png` exists (screenshot)

## Output

After completing the iteration, report:
- What was implemented (coder phase)
- Verification results (verifier phase)
- Files created
- Test results

If ALL success criteria are met, end with:
`<promise>COMPLETE</promise>`

Otherwise, end normally and the next iteration will continue.