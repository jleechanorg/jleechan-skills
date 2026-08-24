---
name: harness-guardrails
description: Harness guardrails derived from recent bug classes and regressions in the WorldArchitect engine.
---

# Harness Guardrails (Added from Bug Analysis)

These guardrails are derived from recent bug classes and regressions in the WorldArchitect engine.

- **Vanilla JS Event Listeners:** Do not use `.bind(this)` inline within `addEventListener` or `removeEventListener`. Always store the bound function reference in the class constructor or initialization block to ensure proper removal and avoid memory leaks or dangling listeners (e.g. `this.boundHandleClick = this.handleClick.bind(this)`).
- **Administrative State Poisoning:** Any administrative override feature (e.g., God Mode, Pre-populated Templates) that bypasses standard LLM state-transition flows MUST explicitly enforce cleanup for orthogonal game states (like `in_combat=False` or `character_creation_in_progress=False`). 
- **DRY Constant Extraction:** When modifying logic that relies on hardcoded lists or tuples (like stripping cooldown fields), you MUST search the repository for duplicates and extract them to a canonical constant to prevent `NameError` hazards during rebases.

- **ZFC Pre-flight Before Any Server-Side Choice Injection:** Before adding ANY `_inject_*`, `_fallback_*`, `_ensure_*`, or `_repair_*` function that touches model output (planning_block, choices, rewards_box), answer all 3 questions: (1) Does the model have explicit instructions for this output in the agent prompt/system instruction? (2) Can a prompt fix this? (3) If yes, fix the prompt FIRST. Only add backend logic after prompt fix fails with evidence. PR #6908: 61 commits from skipping this — root was a missing JSON example in LevelUpAgent prompt.

- **PR Commit Count Alarm:** If a PR accumulates >15 commits on a single behavioral theme (e.g., "planning_block", "finish choices", "level-up state"), STOP before the next backend commit and run `/zfclevel`. A commit count spike on a stable theme reliably indicates symptom-patching rather than root-cause repair. At 30+ commits: require human review of root-cause hypothesis. PR #6908 was the incident: 61 commits before the 5-line root-cause fix was written.

- **Server CANNOT inject planning choices:** The server may persist, normalize, and validate model output. It MUST NOT infer, inject, or synthesize planning choices. `server_generated: True` on a `planning_block` is always a bug signal, not an acceptable state. Any code path that sets `server_generated=True` and then RETURNS that block to the caller is a ZFC violation.

- **Opaque handles are not semantic contracts:** Choice IDs and other transport handles are for lookup, persistence, and migration compatibility only. Legacy IDs such as `level_up_now`, `finish_level_up_return_to_game`, and `custom_action` may remain exact compatibility handles, but new code MUST NOT infer domain, modal ownership, stage, allowed/scrubbed status, or execution behavior from ID names, prefixes, labels, CSS classes, or enum strings. Resolve a submitted handle against the persisted structured choice, then use explicit schema-owned fields such as `intent.domain`, `intent.operation`, or `execution.freeze_time`. If those fields are missing, fix the model prompt/schema or fail closed; do not expand allowlists as the primary repair.

- **Playwright UI Testing & Pre-Push Validation:** When introducing any new browser, selenium, or Playwright tests for Gate 6 evidence:
  1. *Pytest Integration:* Never use standalone `.py` scripts with `sys.exit()`. Always wrap browser checks in standard pytest classes/methods (`test_*`).
  2. *Dynamic Path Resolution:* Always resolve local files using absolute paths via `os.path.dirname(os.path.abspath(__file__))`. Never use relative `../` or `file://./` URLs which fail on CI runners.
  3. *Error visibility and skip paths:* Import-skip when Playwright is unavailable using `pytest.importorskip("playwright.sync_api")`. Do not use broad exception suppressions that hide actual navigation timeouts or setup errors.
  4. *Pre-Push Verification:* Eagerly run the specific targeted test locally via `./vpython -m pytest <path_to_new_test>` and verify it passes before pushing.
