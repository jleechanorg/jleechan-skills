---
name: test-realistic
description: Test a real user journey from a story, issue, diff, or request. Find the acceptance criteria, ask a cold reviewer for manual cases, run them, and report evidence for each outcome.
---

# Test realistic

1. **Find the story and target.** Read repository instructions and the affected user stories. If this skill was loaded from a shared install, also read the repository's `.claude/skills/test-realistic/SKILL.md` when it exists and resolves to a different file. Treat that file as the project profile; read it, do not invoke a second slash command. Use the requested surface and revision. Ask the operator only when the missing answer would change the goal, permission, or what counts as a pass.
2. **Get a cold test plan.** Give one independent subagent or static reviewer the story, visible starting state, target and holds, without the implementation or expected verdict unless needed to understand the contract. Request a human-runnable Markdown checklist: setup, action, observable result, and high-value failure or recovery cases. The reviewer neither operates the environment nor grades its own plan.
3. **Run the cases.** The main agent runs the checklist as an ordinary user on the requested surface using an authorized test identity and isolated fixtures. Check the served revision before action. Run harmless cases first; isolate risky actions and respect holds, capacity, spending limits, and real-account boundaries. A sweep may split independent cases among authorized browser personas without sharing a mutable fixture. Do not simulate missing services, swap environments, or use auth bypass to pass a real acceptance case.
4. **Capture and judge.** For UI claims, use the project's evidence standards for actual before/after frames or continuous video when behavior changes over time. For backend claims, capture the sanitized real request, response, and persisted readback when state matters. Tie every claim to the revision, surface, case, and artifact. Report each criterion as pass, fail, or blocked with a reason and evidence link. Coverage or a click count alone is not correctness.

Minimum run record: target and served revision; test surface and fixture class; the checklist; observations and evidence; a per-case verdict. No mandatory scenario schema or extra setup for an interactive run. If the operator requests the automated persona runner, open [the optional batch runner](SWARM_RUNNER.md); it has a separate adapter and machine-capture contract.
