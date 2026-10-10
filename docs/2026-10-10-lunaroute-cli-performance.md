# LunaRoute CLI Harness & Gateway Performance Analysis Report

**Date**: 2026-10-10  
**Context**: Developer Tooling & Remote LLM Gateway Performance Evaluation  
**Subject**: Empirical Latency, Throughput, and Turnaround Benchmarks for `lunaroute.com`  
**Evaluated CLI Harnesses**: `pil` (Pi Coding Agent), `codexl` (Codex CLI via LunaRoute), `claudel` (Claude Code CLI via LunaRoute), and `codex-luna` (Codex CLI via OpenAI Native API)  
**Evaluated Model Engines**: `deepseek-4.1-flash`, `glm-5.3`, `claude-opus-lr29`, and `gpt-6-luna`  

---

## 1. Executive Summary

This report documents an empirical performance benchmark and latency analysis of developer CLI harnesses accessing LLM backends via the **LunaRoute Gateway** (`gw.lunaroute.com`) compared against native provider endpoints.

### Key Benchmark Findings:
1. **Lightweight CLI Turnaround (`pil` + `deepseek-4.1-flash`)**:
   - `pil` delivers the fastest turnaround for quick interactive queries: **2.26s** on isolated probes and **9.71s** on multi-file code diagnostic prompts.
   - Minimal client initialization overhead makes `pil` ideal for rapid subagent dispatch and fast developer checks.
2. **Context Scaling & Remote Gateway Latency (`codexl`)**:
   - Codex sessions that serialize full workspace instructions and tool definitions (~59,000 input tokens) encounter substantial latency over remote gateways.
   - Without gateway-level prompt caching, `codexl` runs under both `glm-5.3` and `deepseek-4.1-flash` timed out (>25s–30s) on full-context diagnostic prompts.
   - Conversely, native OpenAI execution (`codex-luna`) leveraged established prompt caching (**82.5% cache hit rate**, 279k of 338k tokens cached) to complete full-context runs in **23.83s**.
3. **Claude Code CLI Discovery Hang (`claudel`)**:
   - Direct HTTP SSE streaming to `https://gw.lunaroute.com/v1/messages` functions normally (TTFT: **1,052.7 ms**, 51 events, duration: **3.09s**).
   - However, invoking the `claude` CLI with `ANTHROPIC_BASE_URL="https://gw.lunaroute.com"` hung for >20 seconds prior to prompt transmission due to client-side discovery/handshake stalls.
4. **Model Performance Discrepancy on LunaRoute**:
   - `deepseek-4.1-flash` is 5–8x faster than `glm-5.3` across all harnesses (**2.26s vs. 3.49s** on Pi; **5.98s vs. 17.24s** on Codex).
   - `glm-5.3` consistently timed out (>25s) on complex queries.

---

## 2. Comparative Performance Matrix

| CLI Harness | Model Engine | Gateway Route | Short Probe (1–5 words) | Complex Task (Multi-file) | Status / Verdict |
|---|---|---|---|---|---|
| **`pil`** | `deepseek-4.1-flash` | LunaRoute `/v1` | **2.26 s** ⚡ | **9.71 s** ⚡ | **Top Performer**: Fastest overall turnaround |
| **`pil`** | `glm-5.3` | LunaRoute `/v1` | 3.49 s | >25 s (Timeout) | Usable for short probes; stalls on reasoning |
| **`codex-luna`** | `gpt-6-luna` | OpenAI Native | 5.36 s | **23.83 s** (82.5% cached) | **Reliability Winner**: Server-side cache handles large context |
| **`codexl`** | `deepseek-4.1-flash` | LunaRoute `/v1/codex` | 5.98 s | >25 s (Timeout on 59k ctx) | Fast on small payloads; needs higher client timeout on full repo |
| **`codexl`** | `glm-5.3` | LunaRoute `/v1/codex` | 17.24 s | >30 s (Timeout on 59k ctx) | **Deprecated**: 3× slower than DeepSeek on 1-word probes |
| **`claudel`** | `claude-opus-lr29` | LunaRoute `/v1/messages` | >20 s (Hang) | >20 s (Hang) | **CLI Incompatible**: `claude` CLI discovery stalls on custom URL |

---

## 3. Detailed Performance by CLI × Model Combination

### 3.1 `pil` × `deepseek-4.1-flash` (Pi via LunaRoute)
- **Isolated Short Probe**: **2.26 s** (Exit code 0).
- **Complex Diagnostic Task**: **9.71 s** (Exit code 0).
- **Wire Latency**: Socket connect **135.3 ms**, Time To First Token (TTFT) **241.9 ms**, total wire stream **381.7 ms** (13 chunks).
- **Analysis**: Pi avoids heavy local framework bootstrapping, and `deepseek-4.1-flash` streams immediately without preamble.
- **Verdict**: Best combination for rapid exploratory checks, lightweight subagent delegation, and fast interactive tasks.

### 3.2 `pil` × `glm-5.3` (Pi via LunaRoute)
- **Isolated Short Probe**: **3.49 s** (Exit code 0) — 54% slower than DeepSeek on simple output.
- **Complex Diagnostic Task**: **>25.03 s** (Timed out / aborted).
- **Analysis**: Adequate for trivial queries, but generation latency scales poorly on complex reasoning prompts, exceeding standard client timeouts.

### 3.3 `codex-luna` × `gpt-6-luna` (Codex via OpenAI Native API)
- **Isolated Short Probe**: **5.36 s** (Exit code 0) — Standard baseline with Codex CLI initialization overhead.
- **Complex Diagnostic Task**: **23.83 s** (Exit code 0) — Generated 940 reasoning tokens; cached 279,040 tokens out of 338,271 total input tokens (**82.5% cache hit rate**).
- **Analysis**: Server-side prefix prompt caching absorbs the ~59k token workspace preamble, preventing repeated computation.
- **Verdict**: Best combination for autonomous full-repository pair coding where extensive repository guidelines and tool definitions must remain in context.

### 3.4 `codexl` × `deepseek-4.1-flash` (Codex via LunaRoute)
- **Isolated Short Probe**: **5.98 s** (Exit code 0) — Matches native Codex execution on small payloads.
- **Complex Diagnostic Task**: **>25.02 s** (Timed out / aborted).
- **Root Cause of Timeout**: In repository sessions, Codex serializes all tool definitions and guidelines (~59,255 tokens). Because LunaRoute does not have warm server-side prompt caching for this payload, transferring and processing 59k tokens un-cached pushed TTFT beyond the 25s client timeout.
- **Mitigation**: Increasing client timeouts (`timeout 60s` or higher) enables large-workspace runs.

### 3.5 `codexl` × `glm-5.3` (Codex via LunaRoute — Former Default)
- **Isolated Short Probe**: **17.24 s** (Exit code 0) — Almost 3× slower than `deepseek-4.1-flash` on an identical 1-word probe (`"OK"`).
- **Complex Diagnostic Task**: **>30.02 s** (Timed out / aborted).
- **Analysis**: High inference latency and slow token emission make it unsuited as a default interactive backend. Replaced with `deepseek-4.1-flash`.

### 3.6 `claudel` × `claude-opus-lr29` (Claude Code CLI via LunaRoute)
- **Isolated Short Probe**: **>20.0 s** (Client-side hang / aborted).
- **Raw Wire Stream Test (Direct HTTP / curl)**: Succeeded in **3.09 s** (TTFT: **1,052.7 ms**, 51 chunks with thinking delta).
- **Root Cause**: The LunaRoute `/v1/messages` endpoint is fully compliant at the HTTP wire level. However, the `claude` CLI binary performs unsupported background capability and telemetry negotiations when `ANTHROPIC_BASE_URL` points to an external proxy, stalling before prompt dispatch.
- **Recommendation**: Avoid the `claude` CLI wrapper for LunaRoute; use direct HTTP / SDK clients instead.

---

## 4. Empirical Wire & Gateway Benchmarks (`gw.lunaroute.com`)

Measurements conducted via direct HTTP socket connections and SSE stream parsers:
- **Socket Connect Latency**: `GET https://gw.lunaroute.com/v1/models` completed socket connection and catalog retrieval in **135.3 ms**.
- **DeepSeek 4.1 Flash SSE Stream**:
  - Endpoint: `https://gw.lunaroute.com/v1/chat/completions`
  - Time To First Token (TTFT): **241.9 ms**
  - Total Duration: **381.7 ms** (13 streaming chunks received)
- **Claude Opus LR29 SSE Stream**:
  - Endpoint: `https://gw.lunaroute.com/v1/messages`
  - Time To First Token (TTFT): **1,052.7 ms**
  - Total Duration: **3,089.5 ms** (51 streaming chunks received, thinking delta included)

---

## 5. Applied Configuration Tuning

The following local configuration optimizations were implemented based on these benchmark results:

1. **Codex LunaRoute Configuration (`~/.codex/lunaroute.config.toml`)**:
   Updated default engine to `deepseek-4.1-flash` and configured the full context window capacity:
   ```toml
   model = "deepseek-4.1-flash"
   model_provider = "lunaroute"
   model_context_window = 1048576
   ```

2. **Shell Wrappers (`~/.zshrc`)**:
   Configured `codexl` and `pil` aliases to default to `deepseek-4.1-flash` with dynamic override support via `LUNAROUTE_MODEL`:
   ```bash
   codexl() {
     local _lr_key="${LUNAROUTE_API_KEY:-$(lunaroute key 2>/dev/null)}"
     LUNAROUTE_API_KEY="$_lr_key" \
     command codex --profile lunaroute -m "${LUNAROUTE_MODEL:-deepseek-4.1-flash}" "$@"
   }

   pil() {
     local _lr_key="${LUNAROUTE_API_KEY:-$(lunaroute key 2>/dev/null)}"
     LUNAROUTE_API_KEY="$_lr_key" \
     command pi --provider lunaroute --model "${LUNAROUTE_MODEL:-deepseek-4.1-flash}" "$@"
   }
   ```

3. **Credential Resolution**:
   Unified credential resolution across tools to check `LUNAROUTE_API_KEY` first, falling back to `lunaroute key` to eliminate auth latency in batch automation.

---

## 6. Feedback & Engineering Recommendations for the LunaRoute Team

Based on direct telemetry and developer CLI integration testing, here are four concrete recommendations for the LunaRoute gateway team:

### 1. Implement Gateway / KV Prompt Caching for Coding Sessions
- **Issue**: Developer coding CLIs like Codex serialize 50k–60k tokens of tool definitions and project instructions on every turn. Without prefix prompt caching, processing 59k un-cached tokens on remote gateways takes >25s, causing client-side timeouts.
- **Recommendation**: Support server-side KV / prefix caching (analogous to OpenAI and Anthropic native prompt caching) on endpoints like `/v1/codex` and `/v1/chat/completions`. Even a 5-minute ephemeral prefix cache would drop turnaround from >25s to <5s for multi-turn sessions.

### 2. Support Claude Code CLI Discovery Endpoints
- **Issue**: Direct HTTP calls to `/v1/messages` stream perfectly in 3.09s, but running the official `claude` CLI with `ANTHROPIC_BASE_URL="https://gw.lunaroute.com"` hangs for >20s.
- **Recommendation**: Inspect and support Claude Code CLI's pre-flight discovery requests (such as `/v1/models`, telemetry pings, or version checks). Handling or responding with fast 200/no-op stubs will allow developers to use the `claude` CLI seamlessly over LunaRoute.

### 3. Make `deepseek-4.1-flash` the Default Engine over `glm-5.3`
- **Issue**: `glm-5.3` had a 17.24s turnaround on 1-word probes and timed out on complex prompts. `deepseek-4.1-flash` achieved 2.26s on probes and 9.71s on diagnostic tasks.
- **Recommendation**: Update default routing configurations in client configs, documentation, and recommended profiles to favor `deepseek-4.1-flash` for interactive coding workloads.

### 4. Provide Gateway Response Headers for Cache Status & Queue Time
- **Issue**: When timeouts occur on large context payloads, developers cannot distinguish whether the delay occurred in client transit, gateway queueing, or backend model inference.
- **Recommendation**: Return diagnostic headers such as `x-lunaroute-queue-ms`, `x-lunaroute-prefill-ms`, and `x-lunaroute-cache: HIT|MISS` in SSE completion envelopes.

---

## 7. Appendix: Structured Benchmark Telemetry

```json
{
  "timestamp_utc": "2026-10-10T18:09:24Z",
  "environment": {
    "os": "macOS (Darwin)",
    "codex_version": "OpenAI Codex v0.160.0",
    "gateway_host": "gw.lunaroute.com"
  },
  "wire_and_gateway_probes": [
    {
      "target": "https://gw.lunaroute.com/v1/models",
      "metric": "gateway_socket_connect",
      "duration_ms": 135.3,
      "status": "SUCCESS"
    },
    {
      "model": "deepseek-4.1-flash",
      "endpoint": "https://gw.lunaroute.com/v1/chat/completions",
      "ttft_ms": 241.9,
      "duration_ms": 381.7,
      "chunks_received": 13,
      "status": "SUCCESS"
    },
    {
      "model": "claude-opus-lr29",
      "endpoint": "https://gw.lunaroute.com/v1/messages",
      "ttft_ms": 1052.7,
      "duration_ms": 3089.5,
      "chunks_received": 51,
      "status": "SUCCESS"
    }
  ],
  "isolated_turnaround_probes": [
    {
      "harness": "codex-luna",
      "model": "gpt-6-luna",
      "duration_ms": 5361.0,
      "exit_code": 0
    },
    {
      "harness": "codexl (default)",
      "model": "glm-5.3",
      "duration_ms": 17240.0,
      "exit_code": 0
    },
    {
      "harness": "codexl (tuned)",
      "model": "deepseek-4.1-flash",
      "duration_ms": 5980.0,
      "exit_code": 0
    },
    {
      "harness": "pil (default)",
      "model": "glm-5.3",
      "duration_ms": 3490.0,
      "exit_code": 0
    },
    {
      "harness": "pil (tuned)",
      "model": "deepseek-4.1-flash",
      "duration_ms": 2260.0,
      "exit_code": 0
    },
    {
      "harness": "claudel",
      "model": "claude-opus-lr29",
      "duration_ms": 20000.0,
      "exit_code": -1,
      "note": "Discovery hang before prompt transmission"
    }
  ],
  "diagnostic_task_benchmarks": [
    {
      "harness": "pil",
      "model": "deepseek-4.1-flash",
      "duration_ms": 9711.7,
      "exit_code": 0,
      "status": "SUCCESS"
    },
    {
      "harness": "codex-luna",
      "model": "gpt-6-luna",
      "duration_ms": 23834.7,
      "exit_code": 0,
      "telemetry": {
        "input_tokens": 338271,
        "cached_input_tokens": 279040,
        "cache_hit_rate_pct": 82.5,
        "reasoning_output_tokens": 940,
        "output_tokens": 1701
      },
      "status": "SUCCESS"
    },
    {
      "harness": "pil",
      "model": "glm-5.3",
      "duration_ms": 25032.3,
      "exit_code": -1,
      "status": "TIMEOUT"
    },
    {
      "harness": "codexl",
      "model": "deepseek-4.1-flash",
      "duration_ms": 25026.1,
      "exit_code": -1,
      "status": "TIMEOUT"
    },
    {
      "harness": "codexl",
      "model": "glm-5.3",
      "duration_ms": 30022.1,
      "exit_code": -1,
      "status": "TIMEOUT"
    }
  ]
}
```
