# Gemini 3 API (google-genai) - Usage Notes

Use this when wiring Gemini 3 models in the Python SDK to avoid outdated params.

## ThinkingConfig (Gemini 3)

Use the google-genai SDK `ThinkingConfig` fields (thinking_budget, include_thoughts).

```python
from google import genai
from google.genai import types

client = genai.Client()
response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents="Explain how AI works.",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=1024),
    ),
)
print(response.text)
```

Notes:
- `ThinkingConfig` fields are `thinking_budget` and `include_thoughts` in the current SDK.
- Use a non-trivial budget when enabling thinking for Gemini 3 models.

## Code execution tool (Gemini API)

Enable code execution via tools in GenerateContentConfig:

```python
from google import genai
from google.genai import types

client = genai.Client()
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Compute the sum of the first 50 primes using code.",
    config=types.GenerateContentConfig(
        tools=[types.Tool(code_execution=types.ToolCodeExecution)],
    ),
)

for part in response.candidates[0].content.parts:
    if part.executable_code is not None:
        print(part.executable_code.code)
    if part.code_execution_result is not None:
        print(part.code_execution_result.output)
```

## Structured JSON output (response_mime_type)

Gemini supports structured JSON outputs via response_mime_type and schema.
Gemini 3 can combine structured outputs with built-in tools, including code execution.

```python
from google import genai
from google.genai import types
from pydantic import BaseModel

class Result(BaseModel):
    summary: str

client = genai.Client()
response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents="Summarize this text in one sentence.",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=Result.model_json_schema(),
    ),
)
```

## Checklist for Gemini 3 integrations

- Use thinking_config with thinking_level (Gemini 3).
- Enable code execution via tools=[types.Tool(code_execution=types.ToolCodeExecution)].
- Use response_mime_type="application/json" (and optional response_json_schema) for JSON mode.
- Extract code execution evidence from response parts (executable_code/code_execution_result).
