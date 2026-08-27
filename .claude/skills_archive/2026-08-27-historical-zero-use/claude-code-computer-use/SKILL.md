---
name: claude-code-computer-use
description: Use Claude Code to run computer-use style UI automation loops with screenshot → decide → act cycles, safety guardrails, and step-bounded execution. Trigger when the user asks to make agents do Claude computer-use behavior, desktop/browser UI control, click/type/scroll automation, or iterative visual task execution in Claude Code.
---

# Claude Code Computer Use

Run Claude Code as a bounded UI-control agent that observes screenshots, takes one action, re-checks state, and repeats until success or stop conditions.

## Required loop

1. Restate the user goal in one sentence.
2. Define a max step budget (default 20).
3. For each step, do exactly one UI action.
4. After each action, capture a fresh screenshot.
5. Verify expected change before continuing.
6. Stop on success, ambiguity, or budget exhaustion.

## Tool contract to enforce

Require these tool primitives (or closest equivalents):

- `screenshot()`
- `click(x,y)` / `double_click(x,y)`
- `type(text)` / `key(combo)`
- `scroll(delta)`
- Optional: `ocr(region)` / `accessibility_tree()`

Never take multiple UI actions in a single reasoning step.

## Safety policy

- Allowlist app/site scope before starting.
- Ask before destructive actions (delete, send, purchase, publish, submit).
- If target is unclear for 2 consecutive steps, pause and ask human.
- Log every step with: intention, action, result.

## Claude Code invocation pattern

Use non-interactive Claude Code mode for deterministic logs:

```bash
claude --print --permission-mode bypassPermissions "<task prompt>"
```

Task prompt template:

```text
You are controlling a UI via tools.
Goal: <goal>
Allowed scope: <apps/sites>
Max steps: <N>
Rules:
- One action per step.
- After each action, screenshot and verify.
- If uncertain for 2 steps, stop and ask.
- Ask before destructive actions.
Return a step log and final status: success | blocked | needs-human.
```

## Completion criteria

Declare completion only when:

- Goal state is visible in screenshot evidence, or
- You are blocked and provide the exact blocker + required human input.

Always return concise evidence:

- Final status
- Last 3 step logs
- Screenshot/file references (if available)
