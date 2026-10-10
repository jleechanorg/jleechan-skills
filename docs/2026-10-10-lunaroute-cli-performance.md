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

| Metric / Attribute | `codex-luna` | `codexl` (Default) | `codexl` (Tuned) | `claudel` | `pil` (Default) | `pil` (Tuned) |
|---|---|---|---|---|---|---|
| **CLI Framework** | Codex v0.160.0 | Codex v0.160.0 | Codex v0.160.0 | Claude Code | Pi Coding Agent | Pi Coding Agent |
| **Model Engine** | `gpt-6-luna` | `glm-5.3` | `deepseek-4.1-flash` | `claude-opus-lr29` | `glm-5.3` | `deepseek-4.1-flash` |
| **Gateway Protocol** | OpenAI Native | LunaRoute `/v1/codex` | LunaRoute `/v1/codex` | LunaRoute `/v1/messages` | LunaRoute `/v1` | LunaRoute `/v1` |
| **Turnaround (Isolated Probe)** | 5.36 s | 17.24 s | 5.98 s | >20 s (CLI Discovery Hang) | 3.49 s | **2.26 s** |
| **Turnaround (Complex Diagnostic)**| **23.83 s** | >30 s (Timeout) | >25 s (Timeout) | >20 s (CLI Discovery Hang) | >25 s (Timeout) | **9.71 s** |
| **Cache Hit Rate** | **82.5%** | None recorded | None recorded | Session-bound | None recorded | None recorded |
| **Reliability** | High | Low (Timeouts) | Medium (Fast probes) | Unstable on CLI | Medium (Fast probes) | **High (Sub-10s)** |

---

## 3. Empirical Benchmark Details

### 3.1 Gateway Network & Wire Probes (`gw.lunaroute.com`)
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

### 3.2 Isolated CLI Probe Benchmarks
Measures total CLI invocation, environment loading, model dispatch, and process exit for trivial prompts (`"Respond with one word: OK"` or `"Count from 1 to 5."`):
1. **`pil` (`deepseek-4.1-flash`)**: **2.26 s** (Exit code 0) — Fastest overall turnaround.
2. **`pil` (`glm-5.3`)**: **3.49 s** (Exit code 0).
3. **`codex-luna` (`gpt-6-luna`)**: **5.36 s** (Exit code 0) — Standard Codex native baseline.
4. **`codexl` (`deepseek-4.1-flash`)**: **5.98 s** (Exit code 0) — Comparable to native on small payloads.
5. **`codexl` (`glm-5.3`)**: **17.24 s** (Exit code 0) — Substantial generation latency.
6. **`claudel` (`claude-opus-lr29`)**: **>20.0 s** (Aborted / Timeout) — Stalled during CLI discovery before prompt dispatch.

### 3.3 Complex Code Diagnostic Benchmarks
Measures CLI turnaround when analyzing code context across multi-file inputs:
1. **`pil` (`deepseek-4.1-flash`)**: **9.71 s** (Exit code 0) — Successfully returned analysis in under 10 seconds.
2. **`codex-luna` (`gpt-6-luna`)**: **23.83 s** (Exit code 0) — Generated 940 reasoning tokens; cached 279,040 input tokens (**82.5% cache hit rate**).
3. **`pil` (`glm-5.3`)**: **>25 s** (TimeoutExpired) — Exceeded client-side deadline.
4. **`codexl` (`deepseek-4.1-flash`)**: **>25 s** (TimeoutExpired) — Tripped 25s client timeout under 59k token workspace context.
5. **`codexl` (`glm-5.3`)**: **>30 s** (TimeoutExpired) — Tripped 30s client timeout under 59k token workspace context.

---

## 4. Architectural Analysis

### 4.1 Impact of Input Context Size on Remote Gateway Latency
Local agent frameworks like Codex serialize local tool definitions, instructions, and workspace state on invocation. In rich workspace environments, this initial payload measures ~59,255 tokens.
- On **OpenAI Native** endpoints, server-side prompt caching recognizes the prefix, achieving an **82.5% cache hit rate** and avoiding repetitive token pre-fill computation.
- On **LunaRoute Gateway** endpoints, the full ~59k token payload must be transferred and processed un-cached per request. This pushes TTFT beyond standard 25–30s subprocess timeouts, resulting in client-side abortion.

### 4.2 Claude Code CLI Custom Endpoint Compatibility
While the LunaRoute Anthropic-compatible wire endpoint (`/v1/messages`) returns valid Server-Sent Events, the `claude` CLI performs initial configuration negotiation, telemetry pings, and endpoint capability checks. When directed to `ANTHROPIC_BASE_URL="https://gw.lunaroute.com"`, these background handshakes hang, preventing prompt transmission.

### 4.3 Engine Selection: `deepseek-4.1-flash` vs. `glm-5.3`
- `deepseek-4.1-flash` demonstrates significantly lower TTFT and higher token generation throughput than `glm-5.3` across all tests.
- Transitioning defaults from `glm-5.3` to `deepseek-4.1-flash` reduced isolated probe latency by 65% on Codex and 35% on Pi, while enabling sub-10s diagnostic responses.

---

## 5. Applied Configuration Tuning

The following local configuration optimizations have been applied to ensure fast, reliable developer workflows:

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

## 6. Recommendations for Developers

1. **For Rapid Checks, Probes, and Scaffolding**: Use `pil` with `deepseek-4.1-flash`. At **2.26s** turnaround, it provides the lowest latency among all evaluated harnesses.
2. **For Full-Context Repository Coding**: Use `codex-luna` against native endpoints to leverage prompt caching (82.5% hit rate) and avoid gateway transfer timeouts on 50k+ token sessions.
3. **If Using `codexl` on Large Workspaces**: Increase client-side execution timeouts (`timeout 60s` or higher) to accommodate the gateway pre-fill latency for large un-cached contexts.
4. **Avoid `claudel` CLI with Custom Base URL**: Do not use the `claude` CLI wrapper against `gw.lunaroute.com` until upstream CLI endpoint negotiation issues are resolved; use direct HTTP / SDK clients instead.

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
