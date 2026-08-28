# Simplification

Use this reference after behavior is proven, not instead of behavior proof.

The goal is to challenge the changed code for unnecessary complexity before calling the work done.

## Scope

- Focus on files touched in the current task
- Expand only when the changed code clearly exposes nearby duplication or confusion that should be cleaned up now
- Preserve behavior exactly; this is a shape pass, not a feature rewrite

## Questions

Ask these in order:

1. Does the implementation match the language, framework, and design patterns already used in this repo?
2. Is any part of the solution duplicated, nearly duplicated, or split across helpers that should be one explicit path?
3. Is there dead code, an unused export, a stale branch, or a compatibility path that should just be deleted?
4. Are there abstractions, wrappers, or helpers that exist only to make generated code look organized?
5. Is the code relying on `any`, unsafe `as`, boundary-leaking `unknown`, or scattered validation where parsing at the boundary should provide typed evidence instead?
6. Are recoverable failures classified intentionally, or is a generic catch-all forcing users and operators to guess what happened?
7. Does the surfaced error help the user recover when recovery is possible, without dumping raw internals?
8. Would removing comments make the code harder to understand, or would clearer naming and structure remove the need for them?
9. If a brand new agent opened this file tomorrow, could it follow the flow and safely extend it without reverse-engineering hidden intent?

## Improve

- Prefer explicit names over explanatory comments
- Prefer one obvious control flow over dense indirection
- Prefer deleting dead branches, unused exports, and duplicate helpers over preserving them "just in case"
- Prefer parsed boundaries and domain types over casts and scattered defensive checks
- Prefer specific typed errors, codes, or tagged variants over catch-all strings and ambiguous booleans
- Prefer user-facing errors that suggest a next step when the user can act
- Prefer local consistency with the repo over importing a new pattern from memory
- Prefer fewer concepts, not just fewer lines

## Avoid

- "Simplifying" by compressing logic into clever one-liners
- Extracting helpers that hide rather than clarify intent
- Keeping comments that merely narrate what the code already says
- Large speculative rewrites when the shape problem is local

## Evidence

When this pass finds issues, tie them to one of these:

- duplicated logic or near-duplicates
- dead code, unused symbols, or stale compatibility paths
- comments that reveal unclear structure
- type escape hatches that disabled a useful safety net
- vague or flattened error paths that hide useful recovery information
- abstractions that add indirection without protecting a boundary
- naming or control flow that a fresh agent would struggle to follow
