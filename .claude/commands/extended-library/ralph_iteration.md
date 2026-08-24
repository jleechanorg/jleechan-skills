---
description: ralph_iteration
type: llm-orchestration
execution_mode: llm-driven
---

# Ralph Iteration Command

This command runs ONE iteration of Ralph against the Amazon Clone benchmark.

## Context

- **Workspace**: `ralph/benchmarks/`
- **PRD**: `amazon_clone_prd.json`
- **Spec**: `amazon_clone_full_design_contract.md`
- **Target**: Generate Amazon clone with captioned video evidence

## What to Do

### Step 1: Read the PRD and Spec
```bash
cd ralph/benchmarks/
cat amazon_clone_prd.json
cat amazon_clone_full_design_contract.md
```

### Step 2: Implement the Amazon Clone

Generate a complete e-commerce application with:
- Product catalog with multiple products
- Search functionality
- Shopping cart
- Checkout flow
- Order confirmation
- API behavior validation
- UI rendering
- Error-state handling

### Step 3: Create Evidence Artifacts

**Required files:**
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

### Step 4: Run Tests

```bash
python3 -m pytest -q
```

### Step 5: Verify All Files Exist

```bash
ls -la evidence/
```

## Success Criteria

1. All expected files exist in the working directory
2. `python3 -m pytest -q` passes (exit code 0)
3. `evidence/amazon_clone_flow.webm` exists (captioned video)
4. `evidence/final_order_confirmation.png` exists (screenshot)

## Output

After completing the iteration, report:
- What was implemented
- What files were created
- Test results
- Any blockers or issues

If ALL success criteria are met, end with:
`<promise>COMPLETE</promise>`

Otherwise, end normally and the next iteration will continue.