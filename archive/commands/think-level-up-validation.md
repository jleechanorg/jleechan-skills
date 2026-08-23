---
description: /think-level-up-validation — evaluate level-up completeness and editability proof
type: analysis
execution_mode: immediate
---

# /think-level-up-validation

Read `.claude/skills/level-up-validation/SKILL.md` and apply it to `$ARGUMENTS`.

Use this command to evaluate whether a level-up flow proves:

- all automatic gains and player-selectable decisions were found;
- recommendations were auto-selected before finish;
- every recommendation can be changed via planning-block clicks;
- every recommendation can be changed via free-form text while the modal stays active;
- finish commits exactly once and resumes real story choices.

Return the verdict using the skill's verdict template.
