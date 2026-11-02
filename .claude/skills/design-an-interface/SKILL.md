---
name: design-an-interface
description: Compare alternative module or API interface designs before implementation, especially when the first proposed shape may hide complexity or make misuse easy.
---

# Design an interface

Use this skill to explore interface shape before implementation. The aim is to
find an interface that is simple to use correctly, hides meaningful complexity,
and fits the actual callers and constraints.

## Gather the constraints

Identify the problem the module solves, its callers, key operations, compatibility
requirements, performance constraints, and what should remain internal. Inspect
nearby interfaces so the alternatives fit the existing system.

## Develop alternatives

Generate at least two meaningfully different interface shapes. Vary the tradeoff:
for example, minimize operations, optimize the common case, or provide broader
flexibility. Use bounded independent reviewers or subagents only when available,
authorized, and useful for genuinely independent alternatives; concurrency is
optional. If delegation is unavailable or wasteful, draft the alternatives
directly and state the assumptions behind them.

For each design, show its signature, a short usage example, the complexity it
hides, and its main tradeoff. Do not implement the design unless implementation
is part of the user's request.

## Compare and recommend

Compare the alternatives on:

- Simplicity of the public surface and ease of correct use
- Whether it is focused or over-generalized for the known use cases
- Whether it permits efficient, understandable implementation
- How much complexity it hides behind the interface
- Compatibility with existing callers and conventions

Recommend the best fit and explain the key tradeoff and any unresolved
assumption. Ask the user only when an essential product choice cannot be
resolved from the request or available context; otherwise make a reversible
recommendation and continue.

## Avoid

- Alternatives that differ only in naming or minor syntax
- A broad interface whose implementation is still shallow or awkward
- Presenting an unranked list without a recommendation
- Treating this exploration as approval to implement or change unrelated code
