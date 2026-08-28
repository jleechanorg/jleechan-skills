# Color Palette & Brand Style — Dark Factory

**This is the single source of truth for all colors and brand-specific styles in Dark Factory diagrams.** Every color carries semantic meaning. Do not use a token for a purpose other than the one listed.

This palette is shared with `docs/diagram-color-semantics.md` in the dark-factory repo — the Graphviz `.dot` and the Excalidraw renderer must agree, otherwise a node's color in a pipeline preview disagrees with its color in the README.

---

## Shape Colors (Semantic)

Colors encode **what** a node is in the system, not decoration. Each token has one meaning.

### Component layer (the 3-layer convergence + operator isolation)

| Semantic Purpose | Fill | Stroke | Meaning |
|------------------|------|--------|---------|
| **Engine** | `#d1fae5` | `#065f46` | Pipeline engine / runner (`runner/*.py`, `.dot` parser) — Layer 1 of the convergence |
| **Agent** | `#dbeafe` | `#1e3a8a` | External coding agent (Claude Code, Codex, Antigravity, AO) — Layer 2 of the convergence |
| **LLM** | `#ede9fe` | `#5b21b6` | LLM client / inference gateway (OpenClaw, wafer, thinclaw MCP) — Layer 3 of the convergence |
| **Gate** | `#fef3c7` | `#92400e` | Gate / verdict node (`/es`, `/er`, `code_standards`, public acceptance) — decision / check |
| **Holdout** | `#fee2e2` | `#991b1b` | Sealed holdout / evaluator (`holdout_eval` node) — adversarial, structurally blind to the implementer |
| **Human** | `#e5e7eb` | `#374151` | Human operator / `human_gate` node — what the engineer sees and decides |
| **Decision** | `#fde68a` | `#a16207` | Diamond / conditional branch (e.g. `acc -- pass ?` decision) — control flow only |
| **Start/Exit** | `#a7f3d0` | `#047857` | Pipeline `start` / `exit` node — entry and terminal |

**Rule:** Always pair a darker stroke with a lighter fill for contrast. Engine teal, Agent blue, LLM purple, Gate amber, Holdout red, Human slate — these six tokens cover ~95% of dark-factory diagrams.

### Verdict layer (outcomes of a gate / evaluator)

| Semantic Purpose | Fill | Stroke | Meaning |
|------------------|------|--------|---------|
| **Pass** | `#bbf7d0` | `#15803d` | Verdict = pass / success — node continues to next stage |
| **Warn** | `#fef9c3` | `#a16207` | Verdict = warn — proceed with annotation |
| **Fail** | `#fecaca` | `#b91c1c` | Verdict = fail — node routes to `fix` loop |
| **Error** | `#e9d5ff` | `#6d28d9` | Verdict = error (infra crash, not a real failure) — Healer groups these separately |

### Verdict layer is for *results*; component layer is for *roles*. Do not mix.

A `holdout_eval` node is **red (Holdout role)** even when it returns `pass`. The "verdict color" lives in the edge label or a small badge, not in the node itself.

---

## Text Colors (Hierarchy)

| Level | Color | Use For |
|-------|-------|---------|
| Title | `#0f172a` | Diagram title, layer labels ("Layer 1 — Pipeline engine") |
| Subtitle | `#1e40af` | Subheadings, phase labels ("Phase 2 · Factory execution") |
| Body/Detail | `#475569` | Descriptions, annotations, code snippets |
| On light fills | `#1f2937` | Text inside any of the light-fill component tokens |
| On dark fills | `#f8fafc` | Text inside evidence artifacts only |

---

## Evidence Artifact Colors

Used for code snippets, `.dot` excerpts, and other concrete evidence inside technical diagrams.

| Artifact | Background | Text Color |
|----------|-----------|------------|
| Code / `.dot` snippet | `#0f172a` | syntax-colored per language |
| JSON / data example | `#0f172a` | `#22c55e` (green) |
| Verdict badge (e.g. "verdict: pass") | `#bbf7d0` | `#15803d` |

---

## Arrows & Lines

| Element | Rule |
|---------|------|
| Conditional flow (`acc -- pass`) | **Verdict color of the outcome** (e.g. green for pass, red for fail) |
| Unconditional flow | Stroke color of the **source** node's component layer |
| Isolation boundary (dotted cross) | `#991b1b` (Holdout red) at `strokeStyle: "dashed"` |
| Timeline dot | Fill of the node it represents |

---

## Background

| Property | Value |
|----------|-------|
| Canvas background | `#fefefe` (off-white, not pure white) |
| Frame / layer box fill | `#f8fafc` (slate-50) |
| Frame stroke | `#cbd5e1` (slate-300), `strokeStyle: "dashed"` |

---

## Forbidden (do not use these for component nodes)

- `#ec4899` (hot pink) — reserved for danger / override prompts in evidence
- `#facc15` (raw yellow) — too saturated; use `#fde68a` (Decision) instead
- Pure black `#000000` or pure white `#ffffff` — always use the slate scale
- More than 8 distinct fills in one diagram — if you need more, you are conflating layers

---

## Why this palette exists

A reader of a dark-factory diagram should be able to tell, at a glance, **what role each node plays in the system** without reading labels. Engine teal + Agent blue + LLM purple + Holdout red is the entire 3-layer convergence story in four colors. Adding a gate color tells them where the system makes a decision. Adding a verdict color tells them whether the decision was pass/fail/error. That's the whole taxonomy — anything else is decoration.
