# Specialist commands and templates

Scoped reference for `parallelize-to-ceiling`. The entry `SKILL.md` keeps every
rule, threshold and gate; this file holds only exact commands, flag values and
copy-paste templates that those rules point to. Nothing here relaxes a rule in
the entry file; if the two disagree, the entry file wins.

## Memory admission probes

macOS available memory (free + inactive + purgeable + speculative, not free
alone):

```bash
vm_stat | awk -v ps=$(sysctl -n hw.pagesize) '/Pages free/{f=$3}
  /Pages inactive/{i=$3} /Pages purgeable/{p=$3} /Pages speculative/{s=$3}
  END{gsub(/\./,"",f);gsub(/\./,"",i);gsub(/\./,"",p);gsub(/\./,"",s);
  printf "%.1f GB available\n",(f+i+p+s)*ps/1073741824}'
```

Pressure and top-RSS attribution (attribute the pressure before reacting):

```bash
sysctl kern.memorystatus_vm_pressure_level
ps -Ao rss,comm -m | head
```

Swap is evidence, not a defer tier. If available memory is low, sample twice,
seconds apart, and compare `used`:

```bash
sysctl vm.swapusage; sleep 5; sysctl vm.swapusage
```

Thresholds (heuristics, recalibrate per host) are owned by the entry file's
Resource admission gate: available <4GB or pressure 4 defers new heavy work;
4-8GB or pressure 3 (with at least 4GB available) reduces lane count; >8GB and
pressure <=2 spawns normally. Never gate on `vm.swapusage` used/total.

Never fork a multi-minute CLI delegation (`agy`, `codex`, `claude -p`) as a
foreground Bash call: always `run_in_background` with an explicit timeout, then
read the output file on the task notification.

## Two-agent pair handoff template

```text
PAIR TASK: <bounded task and explicit file scope>
CODER: follow `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-coder.md`; implement and signal IMPLEMENTATION_READY with `Revision: <exact git SHA>` and `Worktree: <absolute path>`.
VERIFIER: follow `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-verifier.md`; independently verify the handed-off revision and signal VERIFICATION_COMPLETE or VERIFICATION_FAILED.
FALLBACK: governed by the "Fallback precedence" and "Codex model routing" sections of `${CLAUDE_HOME:-$HOME/.claude}/skills/parallelize-to-ceiling/SKILL.md`; preserve isolation and independent verification. Never use 5.6 models.
```

## Gemini Flash lane flags

Applies the Gemini Model Invariant in the entry file (never Gemini 3.1 Pro or
older Pro models; never `Model: "inherit"` for bounded subagent lanes):

- AGY CLI (`agy`): pass `--model gemini-3.8-flash-high` (or
  `gemini-3.8-flash-medium` / `gemini-3.8-flash-low` per `agy models`; alias
  `gemini-3.8-flash`).
- Antigravity native subagents (`invoke_subagent`): pass `Model: "flash"` (or
  `Model: "flash_lite"` for simple lookups/reads); never leave
  `Model: "inherit"` or `"pro"` on bounded subagent lanes.
