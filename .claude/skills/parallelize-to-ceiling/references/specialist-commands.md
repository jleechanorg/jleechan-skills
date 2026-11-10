# Specialist commands and templates

Scoped reference for `parallelize-to-ceiling`. Normative rules live only in the entry
`SKILL.md`; this file holds only exact commands, flag values and copy-paste
templates (template lines restate entry-file rules for pasting). If the two
disagree, the entry file wins.

## Memory admission probes

macOS available memory (free + inactive + purgeable + speculative, not free
alone):

```bash
vm_stat | awk -v ps=$(sysctl -n hw.pagesize) '/Pages free/{f=$3}
  /Pages inactive/{i=$3} /Pages purgeable/{p=$3} /Pages speculative/{s=$3}
  END{gsub(/\./,"",f);gsub(/\./,"",i);gsub(/\./,"",p);gsub(/\./,"",s);
  printf "%.1f GB available\n",(f+i+p+s)*ps/1073741824}'
```

Pressure and top-RSS attribution:

```bash
sysctl kern.memorystatus_vm_pressure_level
ps -Ao rss,comm -m | head
```

Swap sampling (two samples, seconds apart; interpretation is in the entry gate):

```bash
sysctl vm.swapusage; sleep 5; sysctl vm.swapusage
```

Rules, thresholds and the foreground prohibition live only in the entry file's
Resource admission gate.

## Two-agent pair handoff template

```text
PAIR TASK: <bounded task and explicit file scope>
CODER: follow `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-coder.md`; implement and signal IMPLEMENTATION_READY with `Revision: <exact git SHA>` and `Worktree: <absolute path>`.
VERIFIER: follow `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-verifier.md`; independently verify the handed-off revision and signal VERIFICATION_COMPLETE or VERIFICATION_FAILED.
FALLBACK: if an AGY lane concretely fails, retry that same bounded lane with a Codex subagent using gpt-6-luna; if Luna is unavailable, concretely fails, or lacks capability, use gpt-6.1-terra; only if Terra is unavailable, concretely fails, or lacks capability, use gpt-6.1-sol as final fallback. Advance only after a concrete failure, unavailability, or demonstrated capability gap at the preceding tier; preserve isolation, scope and independent verification. Never use 5.6 models. Use claudem or an own cheap agent only if the ordered Codex route is unavailable.
```

## Gemini Flash lane flags

Values for the Gemini Model Invariant in the entry file:

- AGY CLI (`agy`): pass `--model gemini-3.8-flash-high` (or
  `gemini-3.8-flash-medium` / `gemini-3.8-flash-low` per `agy models`; alias
  `gemini-3.8-flash`).
- Antigravity native subagents (`invoke_subagent`): pass `Model: "flash"` (or
  `Model: "flash_lite"` for simple lookups/reads).
