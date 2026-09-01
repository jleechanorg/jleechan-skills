---
name: ao-model-override
description: Override the model an `ao spawn` worker uses (e.g. force claude-sonnet-4-6 instead of the project default of wafer.ai/GLM-5.1) WITHOUT mutating ~/.hermes/agent-orchestrator.yaml. Use when the user asks for "claude sonnet with AO", "spawn AO with X model", "AO worker but not GLM", or any one-shot model swap. Also use as the canonical reference whenever someone tries to find a `--model` flag on `ao spawn` and is surprised it doesn't exist.
---

# AO Model Override (Without Editing Global Config)

## TL;DR

`ao spawn` has **no `--model` CLI flag and no model env-var override**. Model is resolved purely from config layers in `packages/core/src/agent-selection.ts:103-111`:

```
worker model = project.modelByCli[agent].model
            ?? defaults.modelByCli[agent].model
            ?? project.worker.agentConfig.model
            ?? project.agentConfig.model
            ?? defaults.agentConfig.model
```

To override at spawn time **without touching the user's config**, point `AO_CONFIG_PATH` at a temp YAML that copies the user's config and patches the target project. The bashrc default `AO_CONFIG_PATH=~/.hermes/agent-orchestrator.yaml` is overridden for one process tree only.

## When to Use

Trigger phrases (any of these → reach for this skill):

- "use claude sonnet with AO"
- "spawn AO with [model]"
- "AO worker but not GLM"
- "override AO model"
- "ao spawn --model ..." (user expects a flag that doesn't exist)
- "make this AO worker use [Opus|Sonnet|Haiku|specific model]"
- Any time `tmux capture-pane` of an AO worker shows `GLM-5.1 with high effort` and the user wanted something else

Do NOT use this skill when:

- The user is fine with the project default
- The user explicitly says "modify the config" (then just edit `~/.hermes/agent-orchestrator.yaml`)
- The user wants a different *CLI* (codex, gemini, opencode) — that's `--agent <name>`, not a model override

## What Does NOT Work (and why)

These are tempting dead ends. Save the time:

| Attempt | Why it fails |
|---|---|
| `ao spawn --model claude-sonnet-4-6 ...` | No such flag in `packages/cli/src/commands/spawn.ts`. Options are only `--agent`, `--runtime`, `--project`, `--claim-pr`, `--open`, `--decompose`, `--max-depth`, `--assign-on-github`. |
| `ANTHROPIC_MODEL=claude-sonnet-4-6 ao spawn ...` | `agent-claude-code` plugin builds its `--model` arg from resolved `config.model`, not env. Plugin only reads env for `WAFER_*` / `MINIMAX_API_KEY` auth, never for model selection. |
| `unset ANTHROPIC_BASE_URL` before spawn | The bashrc `ANTHROPIC_BASE_URL=http://localhost:9000` points to **real Anthropic** (transparent proxy — verify with `curl localhost:9000/` → it returns the Anthropic API banner). It is NOT routing to GLM. The plugin strips and resets `ANTHROPIC_BASE_URL` itself based on model name. |
| `--agent wafer` / `--agent minimax` | These are explicit *provider* plugins. They lock you to GLM-5.1 / MiniMax-M2.7 respectively. The opposite of what you want. |

## Why `claude-code` Defaults to GLM in This Setup

Global config `~/.hermes/agent-orchestrator.yaml` has:

```yaml
defaults:
  modelByCli:
    claude-code:
      model: wafer.ai/GLM-5.1
```

`agent-claude-code/src/index.ts:866-889` then routes by **model name**:

- `MiniMax-*` → MiniMax endpoint
- `wafer.ai/*` (`isWaferModel`) → `https://pass.wafer.ai`
- `z.ai/*` (`isZaiModel`) → `https://api.z.ai/api/anthropic`
- anything else (e.g. `claude-sonnet-4-6`) → strips `ANTHROPIC_BASE_URL` and uses Anthropic OAuth

So setting model to a plain Anthropic ID (e.g. `claude-sonnet-4-6`) is sufficient to route to real Anthropic. The hard part is *getting that model into the resolved config* without mutating the user's file.

## The Procedure

### Step 1: Find the project block and pick override layer

`modelByCli` (per-CLI) takes precedence over `agentConfig.model` (per-project). Either works; `modelByCli` is more surgical because it only affects `--agent claude-code` invocations.

### Step 2: Build the temp config

Copy `$AO_CONFIG_PATH` (default `~/.hermes/agent-orchestrator.yaml`) to a tmp file and add the override under the target project. Example using `yq` (preferred) or manual edit:

```bash
SRC="${AO_CONFIG_PATH:-$HOME/.hermes/agent-orchestrator.yaml}"
DST="$(mktemp -t ao-override-XXXX.yaml)"
cp "$SRC" "$DST"

PROJECT=mctrl-test
MODEL=claude-sonnet-4-6

# yq path:
yq -i ".projects.\"$PROJECT\".modelByCli.\"claude-code\".model = \"$MODEL\"" "$DST"

# Verify:
yq ".projects.\"$PROJECT\".modelByCli" "$DST"
```

Without `yq`, edit by hand under the project block:

```yaml
  mctrl-test:
    modelByCli:
      claude-code:
        model: claude-sonnet-4-6
    agentRules: |
      ...
```

### Step 3: Spawn pointing at the temp config

```bash
AO_CONFIG_PATH="$DST" ao spawn -p "$PROJECT" --agent claude-code "<task description>"
```

The bashrc's `export AO_CONFIG_PATH=$HOME/.hermes/agent-orchestrator.yaml` is overridden for this single command's process tree only.

### Step 4: Verify Sonnet actually landed

Within ~5 seconds of spawn:

```bash
SESSION=mt-XXX  # from spawn output
TMUX_SESSION="$(ls ~/.agent-orchestrator/*-${PROJECT}/sessions/ 2>/dev/null | head -1)"  # or grab from spawn output: "Attach: tmux attach -t ..."
tmux capture-pane -p -t "$TMUX_SESSION" -S -200 | grep -iE "model|sonnet|GLM|opus" | head -5
```

Expected line: `Sonnet 4.6 with high effort · Anthropic OAuth` (or similar).
Wrong: `GLM-5.1 with high effort · API Usage Billing` → override didn't take, re-check the YAML path.

Also verify via session metadata:

```bash
cat ~/.agent-orchestrator/*-${PROJECT}/sessions/${SESSION}/*.json 2>/dev/null | jq -r '.runtimeHandle.data.launchCommand' | head -1
```

Should contain `--model 'claude-sonnet-4-6'`.

### Step 5: Cleanup

```bash
rm -f "$DST"
```

Optionally `ao session kill $SESSION` if you only needed to verify, not produce work.

## Helper Script

A canned helper lives at `~/.claude/skills/ao-model-override/spawn-with-model.sh`. Usage:

```bash
~/.claude/skills/ao-model-override/spawn-with-model.sh \
    --project mctrl-test \
    --model claude-sonnet-4-6 \
    --agent claude-code \
    "Add a shout() function and tests under df_demo/"
```

The script handles the temp config build + cleanup automatically and prints the session name on success.

## Don't / Common Mistakes

- ❌ Editing `~/.hermes/agent-orchestrator.yaml` directly for a one-shot test. The user has explicitly rejected this approach (2026-05-21).
- ❌ Reporting "ao spawn doesn't support model override" and stopping. It does via `AO_CONFIG_PATH`; this skill is the workaround.
- ❌ Forgetting to verify the model via tmux capture-pane after spawn. The launch command may silently fall back to a config layer you didn't account for.
- ❌ Trying `--agent codex` when the user asked for "claude sonnet" — codex uses `gpt-5.4`, not Sonnet.
- ❌ Polluting `~/.hermes/agent-orchestrator.yaml` with throwaway model entries. Use the temp-config pattern.

## Related Files

- AO spawn options: `~/project_agento/agent-orchestrator/packages/cli/src/commands/spawn.ts`
- Model resolution: `~/project_agento/agent-orchestrator/packages/core/src/agent-selection.ts:103-111`
- claude-code plugin routing: `~/project_agento/agent-orchestrator/packages/plugins/agent-claude-code/src/index.ts:771-890`
- Config schema: `~/project_agento/agent-orchestrator/packages/core/src/config.ts:287-330`
- Sibling skills: [[ao-operator-discipline]], [[ao-spawn-gate]], [[ao-worker-dispatch]]
