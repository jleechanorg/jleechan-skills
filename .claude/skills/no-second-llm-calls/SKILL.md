---
name: no-second-llm-calls
description: Resolve application LLM request budgets from the active repository policy
---

# Application Request Policy

The active repository owns production LLM request budgets and authorization.
This portable skill imposes no single-call cap, numeric request limit, or new
approval requirement. Resolve the applicable repository policy before making
production request-budget decisions.

Count actual application-to-provider requests when evidence is relevant; do not
infer a violation from a tool phase, wrapper, or separate user actions. Local
coding, subagents, review, tests, and orchestration may use multiple authorized
model calls under their own workflow rules.
