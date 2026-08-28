# Gemini Code Execution + JSON Mode Compatibility

## CRITICAL: Model-Specific Behavior

### Gemini 3 (gemini-3-pro-preview)
**CAN combine code_execution with JSON mode/structured outputs.**

From [Gemini 3 Developer Guide](https://ai.google.dev/gemini-api/docs/gemini-3):
> "Gemini 3 allows you to combine Structured Outputs with built-in tools, including Grounding with Google Search, URL Context, and Code Execution."

### Gemini 2.x (gemini-2.0-flash, gemini-2.5-flash)
**CANNOT combine code_execution with JSON mode/controlled generation.**

Error returned:
```
INVALID_ARGUMENT: Unable to submit request because controlled generation
is not supported with Code Execution tool.
```

## Summary Table

| Model | Code Execution | JSON Mode | Both Together |
|-------|---------------|-----------|---------------|
| gemini-3-pro-preview | YES | YES | **YES** |
| gemini-2.0-flash | YES | YES | **NO** |
| gemini-2.5-flash | NO | YES | N/A |

## Architecture Implications

For Your Project dice rolling:

1. **Gemini 3**: Can use single-phase code_execution + JSON mode
2. **Gemini 2.x**: Must use two-phase JSON-first tool_requests flow
   - Phase 1: JSON mode call, LLM includes `tool_requests` array
   - Phase 2: Execute tools server-side, inject results, second JSON call

## Code Pattern

```python
# Gemini 3: Can enable code_execution with JSON mode
if model_name in GEMINI_3_MODELS:
    enable_code_execution = True  # Safe with JSON mode

# Gemini 2.x: Must disable code_execution when using JSON mode
if model_name in ["gemini-2.0-flash", "gemini-2.5-flash"]:
    enable_code_execution = False  # Would cause INVALID_ARGUMENT
```

## Sources
- [Gemini 3 Developer Guide](https://ai.google.dev/gemini-api/docs/gemini-3)
- [Code Execution Documentation](https://ai.google.dev/gemini-api/docs/code-execution)
- [Structured Outputs Documentation](https://ai.google.dev/gemini-api/docs/structured-output)

## Last Updated
2025-12-16
