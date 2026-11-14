---
name: bead-followup-templates
description: Standardize br bead follow-ups for PR reviews and code reviews so each bead includes exact implementation instructions, API/function signatures, and acceptance criteria.
---

# Bead Follow-up Templates

Use this skill when the user asks to make or update beads for follow-ups, PR review findings, code-standard violations, blockers, safe fixes, `/nextsteps` handoff items, post-merge cleanup, evidence gaps, PR comments, or implementation handoff.

Do not use this skill for ordinary bead listing or closing unless the bead body is being materially updated with implementation instructions.

## Core Rule

A follow-up bead must be implementable without replaying the whole review. Include the concrete problem, exact evidence, exact intended code shape, and objective acceptance checks.

## Command Policy

- In worktrees or feature branches, use `br --no-auto-flush`.
- Do not use `bd`.
- Prefer updating an existing bead when one already tracks the same issue.
- Avoid `--external-ref` collisions: if multiple beads come from the same PR, put the PR URL in the description instead of using the PR URL as `external_ref`.

## Required Bead Sections

Put these sections in the bead description/body:

```markdown
Context:
- PR:
- Current head or commit URL:
- Review/comment/thread URL:
- Evidence path or log:
- Finding:
- File/line evidence:
- Why it matters:
- Staleness note: signatures and file lines verified at <sha>; re-read before implementation.

Implementation:
- Files:
- Current API/function signatures copied from live code:
```python
def public_function_name(
    required_arg: Mapping[str, Any],
    *,
    option: str | None = None,
) -> bool:
    """One-sentence contract."""
```
- Call-site shape:
```python
result = module.public_function_name(source_state, option=selected_id)
```
- Constraints:
- Non-goals:
- Forbidden paths:

Acceptance criteria:
- Standards:
- Static checks:
- Tests:
- Evidence:
- Done when:
```

## Review Follow-up Checklist

For each finding, record:

- Severity: blocker, important safe fix, risky design fix, or evidence-only.
- Source: PR URL, exact head SHA or commit URL, review/comment/thread URL, evidence path/log, and file/line references.
- Verified problem: one concrete paragraph describing the bug, gap, or standards violation.
- Ownership boundary: the module that should own the decision or invariant.
- Safe path: the smallest standards-compliant change that achieves the goal.
- Forbidden path: patterns to avoid, such as private helper calls, prompt prose in Python, keyword/regex semantic routing, or domain inference outside its declared owner.
- Verification: exact `rg`, test, lint, or evidence command expected to prove the fix.
- Staleness note: signatures and file lines were verified at a specific SHA and must be re-read before implementation.

## API Design Rules

- Read the current code before writing the bead. Do not invent function signatures from memory.
- Define public APIs in the owning module before telling future agents to call them.
- Include the actual function signature and a short docstring contract.
- Include at least one call-site example.
- For removals or replacements, include the exact `rg` check proving old usage is gone.
- For `/code-standards` work, name the violated rule and the compliant alternative.
- When the repository declares a domain-specific ZFC companion, cite its applicable ownership boundaries and checks. Do not import a policy from another repository by default.

## Acceptance Criteria Rules

Acceptance criteria must be objective. Prefer checks like:

```bash
rg "old_private_helper|forbidden_pattern" $PROJECT_ROOT/
../vpython path/to/test.py
```

For production changes under `$PROJECT_ROOT/**`, require `/es`-appropriate evidence. Unit tests can support the bead but cannot be the only runtime proof when the behavior touches production LLM, persistence, rewards, streaming, API, or UI paths.
