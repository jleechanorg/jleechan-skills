# Luna & LunaRoute Harness Performance Analysis and CI Gating Report

**Date**: 2026-10-10  
**Repository Context**: Core Web Application & Skills Framework  
**Authors**: Antigravity Gemini Agent & Codex-Luna Primary Pair  
**Review Status**: Revised to address Primary Pair /advice and /web-advice review findings (reproduced verbatim bq_logging_enabled gate, reconciled pil diagnostic accuracy for truncated capture and inaccurate env flag, distinguished aggregate PR-level checks from workflow shard jobs, and verified machine-readable structured benchmark telemetry).

---

## 1. Executive Summary

This report documents the empirical investigation, benchmarking, and resolution of two interdependent engineering concerns:
1. **Resolution of CI Presubmit Regression in Web App Presubmit**: Triage of Presubmit check failures following the gating of BigQuery logging (`bq_logging_enabled()`) under test/dev mode, including prompt-based triage exploration and surgical code resolution by `codex-luna`.
2. **Empirical Benchmarking of Luna / LunaRoute Developer CLI Combos**: A systematic evaluation of `codex-luna`, `codexl`, `claudel`, and `pil` across local developer environments, comparing real-time latency, context limitations, and problem-solving capability under controlled, documented conditions.

---

## 2. Investigation & Resolution of CI Regression

### 2.1 Background & Problem Statement
In the core web application, telemetry fixture pollution caused integration tests to inadvertently write un-mocked rows to production BQ sinks. A safety gate was introduced in `mvp_site/bq_logging.py`:

```python
_TRUTHY_ENV_VALUES = {"1", "true", "yes"}


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY_ENV_VALUES


def bq_logging_enabled() -> bool:
    if _env_flag("BQ_LOGGING_FORCE"):
        return True
    if _env_flag("WORLDAI_DEV_MODE"):
        return False
    if _env_flag("MOCK_SERVICES_MODE"):
        return False
    return True
```

While unit tests for BigQuery sinks were opted in via `BQ_LOGGING_FORCE=1`, `mvp_site/tests/test_end2end/test_streaming_contract_end2end.py` was omitted.

### 2.2 Presubmit Failure Mode & Concrete Artifacts
In GitHub Actions presubmit testing, the shard `Directory tests (core-mvp-3)` failed with:
```
FAIL: test_provider_usage_reaches_bq_through_real_streaming_route (__main__.TestStreamingContractIntegration.test_provider_usage_reaches_bq_through_real_streaming_route)
SYNTHETIC CONTRACT FIXTURE; counters preserve captured null semantics.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "mvp_site/tests/test_end2end/test_streaming_contract_end2end.py", line 534, in test_provider_usage_reaches_bq_through_real_streaming_route
    self.assertEqual(len(provider_rows), 1, rows)
AssertionError: 0 != 1 : []
```
* **Artifact Reference**: Downloaded and verified from CI artifact log `test_streaming_contract_end2end.py.[REDACTED].log`.
* **Mechanism**: Because the streaming contract test ran under `MOCK_SERVICES_MODE=true` without `BQ_LOGGING_FORCE=1`, `bq_logging_enabled()` short-circuited to `False`, preventing the patched `_insert_rows` spy from intercepting the required telemetry event.
* **Secondary Failure**: A separate test shard failed simultaneously due to an ephemeral self-hosted runner process/network disconnection (`"The self-hosted runner lost communication with the server"`), rather than a code assertion error.

### 2.3 Automated Repair via `codex-luna`
The `codex-luna` alias (`codex exec -m gpt-6-luna --config model_reasoning_effort="high"`) was invoked to inspect the failure, apply the minimal diff conforming to repo file standards, and verify GREEN:

```diff
--- a/mvp_site/tests/test_end2end/test_streaming_contract_end2end.py
+++ b/mvp_site/tests/test_end2end/test_streaming_contract_end2end.py
@@ -489,6 +489,7 @@ class TestStreamingContractIntegration(End2EndBaseTestCase):
             return "test-insert-id"
 
         with (
+            patch.dict(os.environ, {"BQ_LOGGING_FORCE": "1"}),
             patch("mvp_site.firestore_service.get_db", return_value=db),
             patch.object(
                 gemini_provider,
```

**Verification Results & Production Sink Isolation**:
* Focused reproducer: `TEST_MODE=mock TESTING=true TESTING_AUTH_BYPASS=true ./vpython -m pytest mvp_site/tests/test_end2end/test_streaming_contract_end2end.py -k test_provider_usage_reaches_bq_through_real_streaming_route` passed in 3.05s (`1 passed, 61 deselected`).
* Multi-test suite validation: `2 passed, 60 deselected in 7.87s`.
* **Production Sink Isolation**: Because `_insert_rows` is explicitly mocked in the test fixture via `patch.object(bq_logging, "_insert_rows", ...)`, setting `BQ_LOGGING_FORCE=1` populates the in-memory test spy without exercising the unmocked network client for that write path.
* **CI Presubmit Validation**: On commit `3dfc3da7cb0` (head of PR #10260), GitHub Actions presubmit testing completed with all 15 aggregate PR-level status checks passing (0 failures). Specifically, within the previously failing workflow "Self-Hosted MVP Shards" (run `38076927377`), the three test-shard jobs succeeded cleanly (`Directory tests (core-mvp-3)` in 7m15s, `core-mvp-2` in 6m16s, and `core-mvp-1` in 6m47s) alongside the successful `Detect Changed Paths` job (with `Harness autonomy checks` skipped per path filters).

---

## 3. Empirical Benchmark of Luna & LunaRoute CLI Combos

### 3.1 Benchmark Methodology & Telemetry Summary
To eliminate speculation, all measurements were conducted using explicit timeouts across isolated runs.
* **Structured Dataset Reference**: Key execution metrics, turnaround durations, exit codes, token telemetry, and representative outputs across wire probes, isolated probes, and diagnostic tasks are cataloged in Section 7 (Appendix: Structured Benchmark Telemetry & Execution Summary) of this report.

The benchmark suite evaluated three distinct phases:
1. **Network & Wire Probing**: Tested gateway socket connect and models catalog retrieval (`GET https://gw.lunaroute.com/v1/models`, 135.3 ms), along with measured SSE streaming chunk metrics (`deepseek-4.1-flash`: TTFT 241.9 ms; `claude-opus-lr29`: TTFT 1052.7 ms, 51 events).
2. **Interactive Probe Task**: Fixed prompts within each tool family (`"Respond with one word: OK"` for Codex, `"Count from 1 to 5."` for Pi), measuring total CLI turnaround.
3. **Diagnostic Reasoning Task**: Evaluated each tool on an identical zero-shot code reasoning prompt:
   > *"In one concise sentence: In mvp_site/bq_logging.py and mvp_site/tests/test_end2end/test_streaming_contract_end2end.py, why does test_provider_usage_reaches_bq_through_real_streaming_route receive 0 BQ rows when MOCK_SERVICES_MODE=true?"*
   * **Evaluation Rubric for Accuracy**:
     - *Pass (100%)*: Identifies both that `bq_logging_enabled()` evaluates to `False` under `MOCK_SERVICES_MODE=true` (suppressing row insertion) AND that the test omitted the `BQ_LOGGING_FORCE=1` override.
     - *Partial*: Identifies write suppression under `MOCK_SERVICES_MODE=true`, but omits the `BQ_LOGGING_FORCE=1` override, introduces inaccurate assertions regarding test mechanics/environment flags, or suffers truncation while exhibiting factual inaccuracies.
     - *Ungradable*: Response was truncated mid-sentence by capture buffers without visible substantive errors, preventing full audit.
     - *Fail / Timeout*: Non-response within timeout or incorrect reasoning.
   * **Timeouts & Capture Buffer**: 25s for Pi and Codex/DeepSeek, 30s for Codex/GLM. Diagnostic harness outputs were captured with a 250-character buffer limit (`out[:250]`); strings below reflect the verbatim captured buffer.

### 3.2 Comparative Performance Matrix

| Metric / Attribute | `codex-luna` | `codexl` (Default) | `codexl` (Tuned) | `claudel` | `pil` (Default) | `pil` (Tuned) |
|---|---|---|---|---|---|---|
| **CLI Framework** | Codex v0.160.0 | Codex v0.160.0 | Codex v0.160.0 | Claude Code | Pi Coding Agent | Pi Coding Agent |
| **Model Engine** | `gpt-6-luna` | `glm-5.3` | `deepseek-4.1-flash` | `claude-opus-lr29` | `glm-5.3` | `deepseek-4.1-flash` |
| **API Wire Protocol** | OpenAI Native | LunaRoute `/v1/codex` | LunaRoute `/v1/codex` | LunaRoute `/v1/messages` | LunaRoute `/v1` | LunaRoute `/v1` |
| **Turnaround (Isolated Probe)** | 5.36 s | 17.24 s | 5.98 s | >20 s (CLI Hang) | 3.49 s | **2.26 s** |
| **Turnaround (Diagnostic Task)**| **23.83 s** | >30 s (Timeout) | >25 s (Timeout) | >20 s (CLI Hang) | >25 s (Timeout) | **9.71 s** |
| **Accuracy on Diagnostic Task**| **Partial** | N/A (Timeout) | N/A (Timeout) | N/A (Hang) | N/A (Timeout) | **Partial (Truncated / Inaccurate Env)** |
| **Observed Cache Hit Rate** | **82.5%** | None recorded | None recorded | Session-bound | None recorded | None recorded |

*Note: The table reflects the empirical measurements recorded in the Appendix. Context window capacities (128k–1M for Codex/DeepSeek, 200k for Claude, 524k for GLM) reflect provider specifications rather than benchmark metrics.*

---

## 4. Architectural Analysis & Response Audits

### 4.1 Context Scaling & Timeout Discrepancies on Remote Gateways (`codexl`)
* **Observed Telemetry & Measurements**:
  * During session initialization in repository environments, Codex CLI serializes the workspace environment, active tool definitions, and repository guidelines (`AGENTS.md`), totaling **59,255 input tokens** (recorded in session telemetry).
  * In isolated 1-word probes (`"Respond with one word: OK"`), `codexl` with `deepseek-4.1-flash` completed in **5.98s** (exit code 0), demonstrating that the remote gateway functions reliably on small payloads.
  * When executing the diagnostic task with full repository session context, `codexl` runs under both `glm-5.3` and `deepseek-4.1-flash` exceeded their client-side timeouts (30s and 25s, respectively) without returning completion tokens (recorded in the Appendix).
  * In contrast, `codex-luna` against native OpenAI endpoints recorded **82.5% cached input tokens** (279,040 of 338,271 cumulative input tokens cached in session telemetry), completing the diagnostic prompt in **23.83s** with high reasoning effort (`model_reasoning_effort=high`, 940 reasoning tokens).
* **Verbatim Response Audits & Rubric Scoring**:
  * **`pil (deepseek-4.1-flash)`** (9.71s turnaround, Score: **Partial (Truncated / Inaccurate Env Var)**):
    > *"Because `bq_logging_enabled()` in `mvp_site/bq_logging.py` explicitly short-circuits to `False` whenever `MOCK_SERVICES_MODE` (or `APP_DEV_MODE`) is truthy, BQ payload logging is skipped entirely — which is exactly why that test sets `MOCK_SERVIC...`"* (250-character buffer capture)
    * **Audit Assessment**: Correctly identifies that `bq_logging_enabled()` in `mvp_site/bq_logging.py` suppresses telemetry logging under mock mode. However, it introduces an inaccurate environment flag by citing `APP_DEV_MODE` (the production gate checks `WORLDAI_DEV_MODE` and `MOCK_SERVICES_MODE`), and the subprocess capture was capped at 250 characters mid-sentence before verifying whether it stated the `BQ_LOGGING_FORCE=1` override. Under the evaluation rubric, asserting an inaccurate environment flag while truncated mid-sentence classifies it as **Partial** rather than full credit or an ungradable pass.
  * **`codex-luna`** (23.83s turnaround, Score: **Partial**):
    > *"With `MOCK_SERVICES_MODE=true`, the route uses the mock provider path and `bq_logging_enabled()` suppresses BQ writes, so no provider-usage rows are inserted; the test forces mock mode off to exercise the real streaming path."*
    * **Audit Assessment**: Correctly identifies that `bq_logging_enabled()` suppresses BQ writes under mock mode, but inaccurately asserts that "the test forces mock mode off" (the PR fix actually sets `BQ_LOGGING_FORCE=1` to allow telemetry insertion while preserving mock services mode). It receives a **Partial** score.
* **Causal Qualification**:
  * The empirical timeouts confirm that `codexl` did not finish within standard client timeouts (25s–30s) when handling full repository sessions.
  * While the correlation with the measured 59,255 total input tokens is consistent with expected processing overhead on remote proxies, gateway-side execution traces were not instrumented to isolate network transit time versus backend queueing or generation time as the sole driver, and cache status on remote proxy runs was not established.

### 4.2 Claude Code CLI Discovery Hangs on Custom Endpoints (`claudel`)
* **Observed Telemetry**:
  * Direct HTTP streaming to `https://gw.lunaroute.com/v1/messages` using Python and `curl` returned a valid Anthropic SSE streaming response in **3.09 seconds** (TTFT: 1,052.7 ms, 51 events, recorded in the Appendix).
  * However, invoking the `claude` CLI directly with `ANTHROPIC_BASE_URL="https://gw.lunaroute.com"` hung for over 20 seconds before prompt transmission, requiring an abort.
* **Causal Qualification**:
  * While direct endpoint wire compatibility is established, the exact mechanism causing the CLI-level hang (such as unsupported discovery endpoints, capability negotiation, or client-side timeouts) remains a hypothesis pending deep packet inspection of the CLI's internal network requests.

### 4.3 Observed Turnaround Differences: GLM-5.3 vs. DeepSeek 4.1 Flash (`pil` & `codexl`)
* **Observed Telemetry**:
  * `glm-5.3`: Required **17.24s** for a 1-word answer and timed out (>25s) on the diagnostic prompt (recorded in the Appendix).
  * `deepseek-4.1-flash`: Completed a short probe in **2.26s** turnaround in Pi, and completed the full code diagnostic prompt in **9.71 seconds** (recorded in the Appendix).
* **Impact & Qualification**:
  * Switching the default model from `glm-5.3` to `deepseek-4.1-flash` eliminated the turnaround timeout bottleneck for lightweight runners (`pil`), delivering sub-10-second end-to-end turnaround on the diagnostic prompt (though accuracy remains unverified due to buffer truncation). These figures reflect observed end-to-end turnaround times in the test harness rather than pure isolated provider inference latency.

---

## 5. Applied Configuration Tuning

To prevent future latency traps and ensure reliable developer workflows, the following configuration updates were applied:

1. **`~/.codex/lunaroute.config.toml`**:
   Updated default model from `glm-5.3` to `deepseek-4.1-flash` with a 1,048,576 context window:
   ```toml
   model = "deepseek-4.1-flash"
   model_provider = "lunaroute"
   model_context_window = 1048576
   ```

2. **`~/.zshrc`**:
   Updated `codexl` and `pil` functions to respect `LUNAROUTE_MODEL` with a default of `deepseek-4.1-flash`, while sanitizing hardcoded token defaults:
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

3. **Execution Semantics & Capability Alignment**:
   * **Context Window Configuration**: `model_context_window = 1048576` aligns the Codex client configuration with the provider's advertised architectural capacity; actual enforceability remains governed by backend gateway runtime limits.
   * **Interactive vs. Subprocess Execution**: The `codexl` shell wrapper invokes `command codex --profile lunaroute ... "$@"`, passing arguments directly through to either interactive sessions (when run with no positional parameters) or batch executions (e.g. `codexl exec ...`), aligning runtime behavior with the benchmark's execution pattern.
   * **Credential Resolution**: API access resolves via `LUNAROUTE_API_KEY` (falling back to `lunaroute key`), ensuring consistent authentication across interactive shell usage and automated scripting.

---

## 6. Recommendations

1. **Autonomous Coding in Rich Repository Context**: `codex-luna` demonstrated reliable execution and prompt-cached turn starts in repository environments with extensive tooling and instructions, benefiting from established prompt caching (82.5% cache hit rate).
2. **Lightweight Turnaround & Fast Probe Harness**: `pil` with `deepseek-4.1-flash` demonstrated rapid turnaround on isolated probes (2.26s) and completed the diagnostic prompt in 9.71s without framework startup overhead. However, because its diagnostic response was truncated mid-sentence and cited an inaccurate environment flag (`APP_DEV_MODE` instead of `WORLDAI_DEV_MODE`), recommendations for complex code diagnosis or unmeasured workflows (such as shell exploration) require full-buffer verification before adoption as a validated diagnostic engine.
3. **Gateway Considerations**: For developer tooling that transmits large contextual payloads (such as repository guidelines and schema definitions), gateway-level prompt caching or relaxed client timeouts would improve completion consistency on remote proxies.

---

## 7. Appendix: Structured Benchmark Telemetry & Execution Summary

The following structured dataset summarizes benchmark execution results, key telemetry, and representative output samples across wire probes, isolated probes, and diagnostic runs. Output strings represent captured buffer substrings and sample events rather than exhaustive wire streams or terminal stderr logs:

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
      "status": "SUCCESS",
      "sample_output": "We need answer simple. Need count from 1 to 5. Just list. En"
    },
    {
      "model": "claude-opus-lr29",
      "endpoint": "https://gw.lunaroute.com/v1/messages",
      "ttft_ms": 1052.7,
      "duration_ms": 3089.5,
      "chunks_received": 51,
      "status": "SUCCESS",
      "sample_event": "data: {\"delta\":{\"thinking\":\"The\",\"type\":\"thinking_delta\"}}"
    }
  ],
  "isolated_turnaround_probes": [
    {
      "harness": "codex-luna",
      "command": "codex exec -m gpt-6-luna --config model_reasoning_effort=\"high\" \"Respond with one word: OK\"",
      "duration_ms": 5361.0,
      "exit_code": 0,
      "stdout": "OK"
    },
    {
      "harness": "codexl (default glm-5.3)",
      "command": "codex exec --profile lunaroute -m glm-5.3 \"Respond with one word: OK\"",
      "duration_ms": 17240.0,
      "exit_code": 0,
      "stdout": "OK"
    },
    {
      "harness": "codexl (tuned deepseek-4.1-flash)",
      "command": "codex exec --profile lunaroute -m deepseek-4.1-flash \"Respond with one word: OK\"",
      "duration_ms": 5980.0,
      "exit_code": 0,
      "stdout": "OK"
    },
    {
      "harness": "pil (default glm-5.3)",
      "command": "pi --provider lunaroute --model glm-5.3 \"Count from 1 to 5.\"",
      "duration_ms": 3490.0,
      "exit_code": 0,
      "stdout": "1, 2, 3, 4, 5"
    },
    {
      "harness": "pil (tuned deepseek-4.1-flash)",
      "command": "pi --provider lunaroute --model deepseek-4.1-flash \"Count from 1 to 5.\"",
      "duration_ms": 2260.0,
      "exit_code": 0,
      "stdout": "1, 2, 3, 4, 5"
    },
    {
      "harness": "claudel (claude CLI)",
      "command": "claude -p \"Respond with one word: OK\" (with ANTHROPIC_BASE_URL=https://gw.lunaroute.com)",
      "duration_ms": 20000.0,
      "exit_code": -1,
      "stdout": "Client-side hang / abort after >20s before prompt transmission"
    }
  ],
  "diagnostic_task_benchmarks": [
    {
      "harness": "codex-luna (gpt-6-luna, reasoning: high)",
      "prompt": "In one concise sentence: In mvp_site/bq_logging.py and mvp_site/tests/test_end2end/test_streaming_contract_end2end.py, why does test_provider_usage_reaches_bq_through_real_streaming_route receive 0 BQ rows when MOCK_SERVICES_MODE=true?",
      "duration_ms": 23834.7,
      "exit_code": 0,
      "stdout": "With MOCK_SERVICES_MODE=true, the route uses the mock provider path and bq_logging_enabled() suppresses BQ writes, so no provider-usage rows are inserted; the test forces mock mode off to exercise the real streaming path.",
      "session_id": "[REDACTED]",
      "telemetry": {
        "input_tokens": 338271,
        "cached_input_tokens": 279040,
        "cache_hit_rate_pct": 82.5,
        "reasoning_output_tokens": 940,
        "output_tokens": 1701
      },
      "accuracy_evaluation": "Partial",
      "evaluation_notes": "Identified that bq_logging_enabled() suppresses BQ writes, but inaccurately claimed the test disables mock mode rather than setting BQ_LOGGING_FORCE=1."
    },
    {
      "harness": "pil (deepseek-4.1-flash)",
      "prompt": "In one concise sentence: In mvp_site/bq_logging.py and mvp_site/tests/test_end2end/test_streaming_contract_end2end.py, why does test_provider_usage_reaches_bq_through_real_streaming_route receive 0 BQ rows when MOCK_SERVICES_MODE=true?",
      "duration_ms": 9711.7,
      "exit_code": 0,
      "stdout": "Because bq_logging_enabled() in mvp_site/bq_logging.py explicitly short-circuits to False whenever MOCK_SERVICES_MODE (or APP_DEV_MODE) is truthy, BQ payload logging is skipped entirely — which is exactly why that test sets MOCK_SERVIC...",
      "accuracy_evaluation": "Partial (Truncated / Inaccurate Env Var)",
      "evaluation_notes": "Identified that bq_logging_enabled() suppresses writes under mock mode, but cited inaccurate APP_DEV_MODE (the gate checks WORLDAI_DEV_MODE and MOCK_SERVICES_MODE) and was truncated at 250 characters before stating whether BQ_LOGGING_FORCE=1 was required."
    },
    {
      "harness": "pil (glm-5.3)",
      "prompt": "In one concise sentence: In mvp_site/bq_logging.py and mvp_site/tests/test_end2end/test_streaming_contract_end2end.py, why does test_provider_usage_reaches_bq_through_real_streaming_route receive 0 BQ rows when MOCK_SERVICES_MODE=true?",
      "duration_ms": 25032.3,
      "exit_code": -1,
      "stdout": "TimeoutExpired after 25s",
      "accuracy_evaluation": "N/A (Timeout)",
      "evaluation_notes": "Failed to return response within allotted client timeout."
    },
    {
      "harness": "codexl (deepseek-4.1-flash)",
      "prompt": "In one concise sentence: In mvp_site/bq_logging.py and mvp_site/tests/test_end2end/test_streaming_contract_end2end.py, why does test_provider_usage_reaches_bq_through_real_streaming_route receive 0 BQ rows when MOCK_SERVICES_MODE=true?",
      "duration_ms": 25026.1,
      "exit_code": -1,
      "stdout": "TimeoutExpired after 25s",
      "accuracy_evaluation": "N/A (Timeout)",
      "evaluation_notes": "Failed to return response within allotted client timeout."
    },
    {
      "harness": "codexl (glm-5.3)",
      "prompt": "In one concise sentence: In mvp_site/bq_logging.py and mvp_site/tests/test_end2end/test_streaming_contract_end2end.py, why does test_provider_usage_reaches_bq_through_real_streaming_route receive 0 BQ rows when MOCK_SERVICES_MODE=true?",
      "duration_ms": 30022.1,
      "exit_code": -1,
      "stdout": "TimeoutExpired after 30s",
      "accuracy_evaluation": "N/A (Timeout)",
      "evaluation_notes": "Failed to return response within allotted client timeout."
    }
  ]
}
```
