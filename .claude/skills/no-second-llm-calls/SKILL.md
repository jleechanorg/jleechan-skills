---
name: no-second-llm-calls
description: One LLM call per user action — include additional context in primary prompt rather than via followup call
---

# No Second LLM Calls

**COMPACTNESS RULE**: Keep this file under 100 lines.

## Tenet

**One LLM call per user action.** If the LLM needs additional context, include it in the primary prompt — not via a followup call.

## Rationale

- Followup calls add latency (5-30s) and cost
- They indicate a design flaw: the primary call didn't have what it needed
- "Defense in depth" patterns create complexity and hidden state

## Anti-Patterns to Avoid

1. **Rewards followup** — was at `world_logic.py:1733` (`_process_rewards_followup`)
   - Primary LLM receives `rewards_pending` in game state
   - Prompts instruct it to include `rewards_box` directly
   - Fix: ensure primary prompt is complete, don't add followup

2. **Deferred rewards check** — `MODE_DEFERRED_REWARDS` is redundant
   - Same as `MODE_REWARDS` with different prompt
   - Fix: use single rewards mode

3. **Entity validation retry** — `entity_validator.py:586`
   - Makes multiple calls when validation fails
   - Fix: make validation part of primary response

## Investigation Protocol

When adding a second LLM call, check:
1. What context is missing from the primary prompt?
2. Can it be added to the system instructions or game state?
3. Is this a pattern that will recur elsewhere?

If a second call is truly needed, document:
- Why it cannot be done in one call
- What would need to change to eliminate it