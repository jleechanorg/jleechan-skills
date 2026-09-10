---
name: superpowers-brainstorming
description: "Use to explore an unresolved product or design question, or when the user requests brainstorming."
---

# Brainstorming Ideas Into Designs

## Overview

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start with the current context and existing decisions. Resolve routine questions
from available evidence, and ask about material uncertainty. Present a concrete
design with the detail needed to assess it. An already approved plan does not need
another brainstorming phase or approval at each section.

## The Process

**Understanding the idea:**
- Check out the current project state first (files, docs, recent commits)
- Ask focused questions when material uncertainty cannot be resolved from the available context
- Prefer multiple choice questions when possible, but open-ended is fine too
- Only one question per message - if a topic needs more exploration, break it into multiple questions
- Focus on understanding: purpose, constraints, success criteria

**Exploring approaches:**
- Compare useful alternatives when material uncertainty remains or the user requests options; do not reopen an already approved choice
- Present options conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why

**Presenting the design:**
- Once you believe you understand what you're building, present the design
- Use sections and detail proportional to the design and requested review
- Honor requested review checkpoints; otherwise collect feedback without pausing each section
- Cover: architecture, components, data flow, error handling, testing
- Be ready to go back and clarify if something doesn't make sense

## After the Design

**Documentation:**
- Write the validated design to `docs/plans/YYYY-MM-DD-<topic>-design.md`
- Use elements-of-style:writing-clearly-and-concisely skill if available
- Commit the design document to git

**Implementation (if continuing):**
- Continue implementation when authorized; for design-only requests, deliver the design
- Use superpowers:using-git-worktrees to create isolated workspace
- Use superpowers:writing-plans to create detailed implementation plan

## Key Principles

- **One question at a time** - Don't overwhelm with multiple questions
- **Multiple choice preferred** - Easier to answer than open-ended when possible
- **YAGNI ruthlessly** - Remove unnecessary features from all designs
- **Explore alternatives when useful** - Compare options for unresolved material choices or at the user's request
- **Review checkpoints** - Pause for requested checkpoints or material unresolved decisions; an approved plan needs no new options phase or per-section approval
- **Be flexible** - Go back and clarify when something doesn't make sense
