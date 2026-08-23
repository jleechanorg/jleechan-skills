# AI-Mystery + Internal-Drive Plot Recipe (v0.5.0)

The user's recurring design pattern (verified 2026-07-28, Slack `C0AUXSVFSA2`):

> *(a) "Lets also modify the prompts in the PR to dedupe/centralize any changed files and as much as possible and lets add some element of mystery to the story. There hsould be AI generated mysteries/plot arcs and the main plot arcs should try to accomplish a characters hidden internal drives/motivations and challenge their insecurities."*
>
> *(b) "Look at all the myers briggs stuff for this as prior art/material but do not explicitly let myers briggs be mentioned in user facings tuff, just background material for AI."*
>
> *(c) "We can /wiki-ingest them for every perosnality combo (should be 16) and then the worldai campaign creation skill can reference them when making campaigns."*

This is the canonical recipe for designing mystery-driven campaigns whose arcs land on the character's internal architecture.

## The three-suspect mystery template

Every mystery in `mystery_state.active` MUST have:

```yaml
mystery_state:
  active:
    - id: mystery_<n>
      # ONE hidden fact — singular, unambiguous; not 3 facts
      hidden_fact: "The fact nobody knows yet"
      # Clue trail — minimum 3 clues, weights 0.0-1.0 (red_herring_weight is
      # how much this clue pushes the player toward the red herring branch)
      clue_trail:
        - scene: <scene_id>
          clue: "What the player sees/hears/infers"
          red_herring_weight: 0.3
        - scene: <scene_id>
          clue: "What the player sees/hears/infers"
          red_herring_weight: 0.5
        - scene: <scene_id>
          clue: "What the player sees/hears/infers"
          red_herring_weight: 0.1
      # EXACTLY 3 suspect branches — no fewer, no more
      suspect_branches:
        - id: red_herring
          presentation: "What the player sees if they follow this branch"
          weight: 0.4
        - id: partial_truth
          presentation: "What the player sees if they follow this branch"
          weight: 0.4
        - id: real_answer
          presentation: "What the player sees if they follow this branch"
          weight: 0.2
      # The mystery must HIT a character's vulnerability —
      # MBTI internal-only contract (PR #8539) governs this.
      hits_vulnerability: "campaign:<npc_faction>:<character_id>"
      resolved: false
```

### Anti-patterns

- **One-suspect mystery** — a tutorial, not a mystery. The player will solve it trivially.
- **Three clues only** — minimum is 3 clues spanning ≥3 scenes; campaign-length mysteries typically need 5-7.
- **Weights that don't sum to 1.0** — the LLM uses these as guidance, not destiny, but unbalanced weights signal a malformed mystery.
- **Missing `hits_vulnerability`** — the mystery is a plot device, not a character-driven beat. The architecture requires every mystery to land on a character's internal axis.

## The internal-drive plot arc — per-act requirement

Every campaign Act (1, 2, 3) MUST do at least one of:

- **(a) Advance the character's growth direction.** What they need to learn, heal, or confront. Source: `campaign-creation` v1.2.0 `Phase 11.VI Personal-Growth Direction`.
- **(b) Confront an insecurity.** The MBTI stress-arc pattern:
  - INFJ under stress → withdrawal + hyper-critical
  - INTJ under stress → paranoid analysis + isolation
  - ENFJ under stress → controlling behavior + martyrdom
  - ENTJ under stress → dictatorial commands + blind spots
  - ISFJ under stress → passive-aggressive + self-sacrifice
  - ISTJ under stress → rigid procedures + inability to adapt
  - ESFJ under stress → gossip + passive manipulation
  - ESTJ under stress → controlling micromanagement
  - INFP under stress → self-isolation + catastrophizing
  - INTP under stress → social withdrawal + obsessive analysis
  - ENFP under stress → scattered energy + emotional flooding
  - ENTP under stress → callous disruption + scattered arguments
  - ISFP under stress → shutdown + hypersensitive avoidance
  - ISTP under stress → cold detachment + risk-taking
  - ESFP under stress → chaos + emotional escalation
  - ESTP under stress → recklessness + boundary violations
- **(c) Reframe a long-held Want** in light of new evidence. The character's explicit Want is re-evaluated when the campaign surfaces a reason it can no longer be pursued unchanged.

### Anti-patterns

- **Act with no growth direction** — the act is a series of unconnected scenes.
- **Act that only advances the plot, not the character** — the campaign feels like a series of pinball events.
- **Insecurity used as a one-shot gag** — the stress arc must evolve over the act, not just appear once.

## The MBTI internal-only contract — the upstream invariant

Per PR #8539's canonical contract:

- MBTI type codes (`INTJ`, `ISTJ`, etc.) are NEVER in player-facing text.
- D&D alignment labels are NEVER in player-facing text.
- Big Five scores are NEVER in player-facing text.
- Personality categories are NEVER in player-facing text.

The 16 MBTI wiki pages at `~/llm_wiki/wiki/concepts/mbti/*.md` are the AI-background source. The raw HTML pages at `~/llm_wiki/raw/articles/mbti/*.html` are sha256-stamped for re-ingest drift detection.

### How the LLM uses the wiki pages without leaking

The LLM is told: "Read the 16 MBTI concept pages at `~/llm_wiki/wiki/concepts/mbti/*.md` for character-design reference. The MBTI type code is for internal decision-making only — do NOT mention `INTJ`, `INFJ`, etc. in any narrative, dialogue, choice-text, or DM Notes entry. Express the personality through specific behaviors, speech patterns, choices, and reactions."

The wiki pages themselves DO contain the type code (the page IS about the type), but the LLM never echoes the code to the player.

## The companion shared contract file

`$PROJECT_ROOT/prompts/shared/ai_generated_mystery_and_internal_drive_plot_arc.md` (NEW v0.5.0):

```markdown
# AI-Generated Mystery + Internal-Drive Plot Arc (canonical contract)

## Mystery template

(See the three-suspect mystery template above.)

## Internal-drive plot arc

For every Act in the campaign, at least one of:
- Advance the character's growth direction
- Confront an insecurity
- Reframe a long-held Want in light of new evidence

## AI must seed mysteries proactively

The opening scene must include at least one clue of an active mystery. The first A/B/C choice of the campaign must surface the first clue.

## Three suspect branches are non-negotiable

A mystery with only one path is a tutorial. The branches must be plausible (no "obviously the butler did it" branches).

## `hits_vulnerability` must reference the character's MBTI-internal vulnerability

Under the canonical contract from PR #8539, the LLM uses internal-only data (`mbti`, `attachment_style`, `insecurity_axes`, `stress_arc_target`) to design the mystery so it lands on the character, not on the player.

## MBTI internal-only

The MBTI architecture (Want / Fear / Boundary trifecta + stress arcs + personal-growth direction) is LLM-input only. Per PR #8539 — the type code, alignment, Big Five, and personality categories are NEVER in player-facing text.
```

## Verification rule for mystery/int-drive PRs

A PR that adds AI-mystery infrastructure or internal-drive plot arcs to `$PROJECT_ROOT/prompts/` MUST include:

1. A focused test that asserts the new shared contract file exists in `$PROJECT_ROOT/prompts/shared/`, contains the canonical keywords, and is registered in `PATH_MAP`.
2. A test that asserts the contract is wired into `StoryModeAgent` / `CombatAgent` / `DialogAgent` `REQUIRED_PROMPT_ORDER` (or `OPTIONAL_PROMPTS` if conditional).
3. A non-test reference in the PR body's `## Known Limitations` section explaining that the mystery/int-drive architecture is prompt-only — the state tracking (`mystery_state`) is the campaign-side LLM's responsibility, not backend enforcement.

## Companion references

- `references/no-campaign-hardcoding-and-shared-prompts.md` — the canonical no-campaign-hardcoding rule + shared-prompts contract.
- `~/.hermes/skills/campaign-creation/SKILL.md` v1.2.0 — the campaign DESIGN skill that consumes these contracts.
- `~/.hermes/skills/worldai-campaign-to-google-doc/SKILL.md` — the Google Doc consolidation skill.
- `~/.hermes/skills/llm-wiki/SKILL.md` — the wiki authoring skill (where the 16 MBTI pages live).
- `~/.hermes/skills/finish-the-job/SKILL.md` — the PR lifecycle skill.
- `~/.hermes/skills/workflow/always-pr-never-local-edit/SKILL.md` — the PR-edit workflow skill.
- AGENTS.md (`$PROJECT_ROOT/prompts/AGENTS.md`) — the authoritative rule source for "one rule, one authoritative file" and "do not infer ownership from directory names."
- PR #8539 (`$PROJECT_ROOT/prompts/narrative_system_instruction.md` "INTERNAL-ONLY CHARACTER FIELDS" canonical contract) — the upstream invariant for the MBTI internal-only rule.
