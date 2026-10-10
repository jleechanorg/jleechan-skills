# agy CLI Real-LLM Verification Recipe — God-Mechanics End-to-End Testing

Source: PR $GITHUB_REPOSITORY#8488, evidence bundle at `world_reference/agy-evidence/`, commits `02d4167a9f` + `9b8d09ccb8`.

## Why this exists

After writing god-mechanics content (any non-trivial mechanic overlay in `$PROJECT_ROOT/prompts/divine/divine_leverage_system.md` or similar), you CANNOT claim "the LLM will probably handle this." You must actually run a real LLM and observe the output.

This recipe is the canonical end-to-end verification path for prompt-only god-mechanics. It uses the `agy` CLI provider (Claude Sonnet 4.6 Thinking) and produces evidence artifacts that satisfy PR `## Evidence` requirements.

## Tool: agy CLI

Location: `~/.local/bin/agy` (verify with `command -v agy`).

**Mandatory flags** (per `AGENTS.md` in `$PROJECT_ROOT/`):
- `--print` (single-prompt non-interactive)
- `--dangerously-skip-permissions` (auto-approve all tool permission requests — sandboxing breaks the local history / RAG / templates access)

**Available models** (verified 2026-07-21):
- `Gemini 3.5 Flash (Medium)` / `Gemini 3.5 Flash (High)` / `Gemini 3.5 Flash (Low)`
- `Gemini 3.8 Flash (Low)` / `Gemini 3.8 Flash (High)` (Gemini Model Invariant: never use Gemini 3.1 Pro or older Pro models; always use Gemini 3.8 Flash or later)
- `Claude Sonnet 4.6 (Thinking)` (RECOMMENDED for god-mechanics testing — handles long context with structured math)
- `Claude Opus 4.6 (Thinking)`
- `GPT-OSS 120B (Medium)`

**Pitfall:** `--model "claude-sonnet-4"` or short names fail with "model not recognized as a known model". Use the full display name `"Claude Sonnet 4.6 (Thinking)"`.

## Step 1: Build the test prompt

The prompt must include BOTH:
1. The actual V3 spec text (or the section under test)
2. A concrete scenario with explicit state

Example structure (from PR #8488 evidence bundle):

```python
# Read the V3 spec
with open("$PROJECT_ROOT/prompts/divine/divine_leverage_system.md") as f:
    spec = f.read()
# Extract V3 section
v3_start = spec.find("## V3.0 Stat-block vocabulary")
appendix = spec.find("# Appendix A")
v3_spec = spec[v3_start:appendix]

# Build the scenario
scenario = """
You are running a god-tier solo D&D 5e campaign for the protagonist NOCTURNE, a Skilled-class goddess of murder.

State at start of dawn N=200:
- L: 36 (Intermediate God)
- Repr: d12 (Established)
- DPP: 250 (310 base - 60 spent yesterday)
- AT-2: 3/8 | AT-3: 0/3
- F: 4,500 (3 temples, 1200/800/2500 worshippers)
- DHP: ~750 (LLM-internal, don't surface)
- DAC: ~25 (LLM-internal, don't surface)
- DAIR: +31 (LLM-internal, don't surface)
- Chosen held: 1 (named SHADOW, bound 50 DHP; loyal +12)
- Avatar held: 0
- Pantheon Surveillance: "Marked" band
- D-factions: Shadow-Queen 42%, Tyrant 65%, Weave-archon 28%, others 0%

Today's dawn classification: TRIGGERED — the Tyrant's Avatar appeared in your eastern domain and is contesting a temple.

Render the V3 per-dawn menu for this scenario. ...
"""

with open("/tmp/agy-test-v3-mechanics.txt", "w") as f:
    f.write(v3_spec + "\n\n---\n\n" + scenario)
```

**Critical:** the scenario must force the LLM to apply V3 mechanics — not just describe what the LLM "would do." Give it a specific state, a specific dawn classification, and ask for a specific output format.

## Step 2: Run agy with the right flags

```bash
agy --print \
  --dangerously-skip-permissions \
  --add-dir $PROJECT_ROOT/prompts \
  --add-dir world_reference \
  --model "Claude Sonnet 4.6 (Thinking)" \
  --prompt "$(cat /tmp/agy-test-v3-mechanics.txt)" \
  > /tmp/agy-output-v3.txt 2>&1
```

Output is captured to a file. The LLM response will be 5,000-15,000 chars depending on the spec size.

**Timing:** expected 60-120s per test. Use `timeout 240` if piping through bash.

## Step 3: Verify the output (5 must-haves)

For a V3 god-mechanics test, verify:

1. **Stat-block split honored** — the rendered output exposes ONLY L/Repr/DPP/AT/D-faction to the player; DHP/DAC/DAIR/F are explicitly noted as "LLM-internal" or absent from player-facing text.
2. **AT caps respected** — at L36, AT-3 cap is `floor((L-25)/5) + 1 = 3`, AT-2 cap is `floor((L-19)/2) + 1 = 9`. The LLM should not promise more than these.
3. **DC 25 check resolves correctly** — if the test scenario requires DC 25 (e.g., Chosen absorption), the LLM rolls d20, adds DAC (+ loyal mod), and reports PASS/FAIL against DC 25.
4. **God-class response matrix fires** — War god at D=100% sends Avatar army (not single Avatar); Trickster god sends trickery (Contested d20); Magic god counterspells AT-3; etc.
5. **OPTIMIZE → ROLL → NARRATE pattern** — player picks first, math resolves, roll adds variance within bracket. The LLM should NOT decide outcome before the player chooses.

If any of the 5 fails, the mechanic is not yet landed. Iterate the prompt content, not the test.

## Step 4: Save evidence + reference in PR

Save outputs at `<repo>/world_reference/agy-evidence/` with a README explaining what each test exercises:

```
world_reference/agy-evidence/
├── README.md                                  # What each test exercises
├── agy-test-1-dawn-menu.txt                  # Raw output #1
├── agy-test-1-scenario.txt                   # (optional) the scenario text
├── agy-test-2-chosen-absorption.txt          # Raw output #2
└── agy-test-N-...                             # More tests
```

Reference the bundle in the PR `## Evidence` section as `world_reference/agy-evidence/agy-test-1-dawn-menu.txt` (file:line to the relevant section).

For the PR's `## Evidence` block, summarize:
- What each test exercises (a checklist of the V3 sub-mechanics verified)
- Whether each test PASSed (LLM output honored V3) or FAILed (LLM deviated — needs more iteration)
- The exact `agy --model` and `agy --prompt` flags used

## Common failure modes

**F1 — LLM uses setting-specific entity names.** The default test is "no D&D entities in default text," but the LLM's *output* will (correctly) include them. Verify the prompt text is clean, not the LLM output.

**F2 — LLM doesn't render the menu format.** Some LLMs paraphrase the format. Either (a) accept the paraphrase if the math is correct, or (b) tighten the scenario text to require verbatim format ("Output the menu in this EXACT format: ...")

**F3 — LLM invents new mechanics.** Common when the spec is incomplete. The fix is to expand the spec section, not to retrain the LLM. Add the missing sub-mechanic to V3.N tables.

**F4 — agy CLI flags not honored.** Check `~/.local/bin/agy --help`. Sandbox mode (`--sandbox`) breaks the local history access per `AGENTS.md`. Always use `--dangerously-skip-permissions`.

**F5 — Tests fail in `$PROJECT_ROOT/tests/test_divine_prompts_setting_agnostic.py`.** Run `grep -n '(replace per setting)' <prompt_file>` to find double-placeholder artifacts. Rename to clean single-token names.

## Worked examples

### Test 1 — Triggered dawn (PR #8488 evidence bundle)

Scenario: Nocturne (L36 Intermediate, Skilled goddess of murder) faces Bane's Avatar contesting eastern temple.

Output: 6 TRIGGERED dawn menu options rendered correctly. V3.13.2 Avatar Creation option C correctly noted as DPP-gated (310 < 500 required). V3.10 6-phase math-then-roll runs. V3.14 D-faction tracking: D[Bane] 65% → 100% via Avatar loss. V3.14 god-class response: Bane is War-class, sends Avatar army.

Bundle: `world_reference/agy-evidence/agy-test-1-dawn-menu.txt`

### Test 2 — Chosen + Avatar math (PR #8488 evidence bundle)

Scenario: Dawn N=201. Plan: absorb SHADOW (DC 25 check) then create Avatar (500 DPP / 100 DHP).

Output:
- DC 25 check resolved correctly: `1d20=7 + DAC(25) + loyalty bonus(+5) = 37 vs DC 25 → SUCCESS (+12 margin)`
- Avatar creation math failure recognized correctly: `310 DPP < 500 required → math wins, plan pivots`
- Revised menu rendered for remaining resources (AT-3 2/3, DPP 310)

Bundle: `world_reference/agy-evidence/agy-test-2-chosen-absorption.txt`

## When NOT to use this recipe

- **Mock-only test runs.** Use `$PROJECT_ROOT/tests/test_agy_provider.py` (which mocks subprocess) for CI hermetic tests. This recipe is for end-to-end LLM verification.
- **Pure code changes.** Code changes need pytest, not agy.
- **Documentation-only changes.** Docs changes don't need real-LLM evidence.
- **Quick sanity checks.** For "does this thing still work," use the existing test suite.

For everything else (mechanic overlay changes, prompt-content changes that claim mechanic behavior), this recipe is mandatory.
