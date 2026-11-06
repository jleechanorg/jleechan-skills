---
name: game-evidence-reviewer
description: Review game/demo video evidence against Ragnarok Online quality standards.
---

# Game Evidence Reviewer Skill

Review game/demo video evidence against the approved visual direction and the
claims the evidence is meant to establish. Ragnarok Online is a quality
reference; it does not define automatic thresholds or approval.

## References

- [[Ragnarok Quality Game Demo Criteria|sources/ragnarok-quality-game-demo-criteria]]
- [Visual Verification](../visual-verification/SKILL.md) owns the currently
  available visual-inspection tools and their limitations. This guide owns the
  game-media identity and frame-coverage protocol below.
- [Design Fidelity Diff](~/.claude/skills/design-fidelity-diff/SKILL.md) owns
  comparison against an approved design artifact.
- Scratch allocation follows
  [Scratch Space](~/.claude/skills/scratch-space/SKILL.md).

## Activation

```text
/game-er [evidence_path]
```

Or invoke when validating game demo evidence.

## Review Procedure

1. Identify the approved visual direction or acceptance criteria and the
   specific claims this media is expected to support. If none is supplied,
   describe observations without inventing product requirements and leave
   product acceptance unproven (**PARTIAL**).
2. Record the media identity and mechanical properties: source SHA-256,
   duration, decoded frame count, frame rate, dimensions, codec, and
   decode/integrity result. Keep temporary outputs in Scratch.
3. Inspect every decoded frame in chronological order, maintain a coverage
   manifest, and disclose any gaps or limitations. Use Visual Verification to
   select a currently available inspection tool and report its limitations.
   Do not use a sample, contact sheet, frame count, or pixel-difference score as
   a substitute for required visual inspection.
4. Assess the visible result against the approved direction. Describe what the
   character and environment actually do and look like. For animation, assess
   whether observed poses form the intended coherent action (such as a walk
   cycle), including contact and recovery poses when relevant. Pixel changes or
   camera movement alone do not establish coherent animation.
5. Report product acceptance separately from evidence/runtime facts. A
   decodable video, motion, dimensions, frame rate, or codec does not establish
   visual quality or product acceptance. Where an approved mock exists, use
   Design Fidelity Diff for the artifact-to-artifact comparison.

## Assessment Areas

Assess only claims relevant to the approved direction and captured behavior:

- **Character and sprite:** readability, pose, silhouette, detail, and fit with
  the approved style.
- **Animation and motion:** whether the visible sequence communicates the
  intended coherent action; note pose, contact, timing, and continuity issues
  that are actually observable. Distinguish character motion from camera or
  scene movement.
- **Environment:** composition, tile or edge continuity, palette, and relation
  to the approved scene direction. A cool, limited, grayscale, or otherwise
  non-warm palette is not a defect by itself.
- **Interaction and game feel:** visible response, collision, or control claims
  only when the recording contains enough evidence to assess them. Do not infer
  responsive controls or wall blocking from movement alone.

Use observed evidence and the approved criteria to explain each assessment.
Do not assign a quality verdict from color counts, pixel counts, image
differences, or other numerical proxies. Mechanical media properties may be
reported as facts, but they do not decide visual quality.

## Verdicts

Assess each required claim as **PASS**, **PARTIAL**, **FAIL**, or
**NOT OBSERVED**, with a concise reason tied to inspected frames and timestamps.

- **PASS** means the required claim is visibly supported against the approved
  direction across the inspected coverage.
- **PARTIAL** means some evidence supports the claim, but a material limitation
  or incomplete coverage prevents a full conclusion.
- **FAIL** means inspected evidence contradicts a required claim or shows a
  concrete defect against the approved direction.
- **NOT OBSERVED** means the recording does not show enough evidence to assess
  the claim.

The overall result is **PASS** only when all required visual claims pass over
the required coverage. Use **PARTIAL** when required claims remain unproven,
coverage is incomplete, or a material limitation remains. Use **FAIL** when a
required claim fails. If no approved criteria or required claim list was
supplied, report observations but leave product acceptance **PARTIAL**; an
empty claim list is not approval. Never convert missing evidence into
approval. A passing media-integrity check is not product acceptance.

## Output Format

```markdown
## Game Evidence Review

**File**: [path]
**Media SHA-256**: [hash]
**Duration**: [value] | **Dimensions**: [width x height] | **Frame rate**: [value] | **Codec**: [value]
**Decoded frames**: [count] | **Integrity**: [result]
**Visual coverage**: [all-frame coverage manifest/ranges and any gaps]
**Approved direction / criteria**: [reference, or not supplied]

### Required Claims
| Claim | Verdict | Visual evidence (frame/time) | Limitation |
|---|---|---|---|
| [claim] | [PASS / PARTIAL / FAIL / NOT OBSERVED] | [observed evidence] | [limitation or none] |

### Visual Findings
- Character and sprite: [observed result or not applicable]
- Animation and motion: [observed coherent action, pose/contact findings, or not observed]
- Environment and style: [observed result against approved direction]
- Interaction and game feel: [observed result or not observed]

## OVERALL: [PASS / PARTIAL / FAIL]
**Reason**: [claims that passed, failed, or remain unproven, with coverage limits]
```

## Critical Rules

1. Inspect every required frame and report the coverage manifest and any gaps.
   Use Visual Verification for available inspection tools and their limits;
   never waive required coverage because sampling is convenient.
2. Use an image-capable route to assess visual claims; numerical pixel or color
   analysis cannot stand in for seeing the frames.
3. Report mechanical media facts separately from visual findings and product
   acceptance.
4. Camera pans, colored noise, or changed pixels do not prove a coherent walk
   cycle. Assess the actual poses and intended action.
5. Judge the actual palette and poses against the approved direction; do not
   fail a clip merely for lacking warm colors or having limited colors.
6. Disclose incomplete visual coverage and leave affected required claims
   PARTIAL or NOT OBSERVED; do not imply full coverage or approval.
