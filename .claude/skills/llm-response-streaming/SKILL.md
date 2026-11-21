---
name: llm-response-streaming
description: Build a Python browser SSE relay for visible text from direct Gemini GenerateContent streaming or OpenRouter Chat Completions; use when implementing or debugging partial output, heartbeats, UTF-8 decoding, or terminal stream errors.
---

# Stream LLM responses to a browser

Keep three layers separate:

1. **Provider adapter.** Consume Google's SDK candidate parts or decode raw bytes from OpenRouter SSE. Yield visible text as it arrives. Keep usage, finish reasons, thoughts and tools out of the visible text.
2. **Server relay.** Open the HTTP response before waiting for the provider. Forward ordered chunks through a bounded queue and send SSE comments while upstream is quiet. Close the upstream iterator on completion or downstream cancellation when control returns to the worker.
3. **Browser consumer.** Append each new sequence once. A protocol `done` closes transport; inspect the finish reason before treating the reply as complete. On an error, retain already displayed text as partial and never replay it automatically.

Use [the integration guide](references/integration.md) for setup, Flask and browser wiring, the event contract, and evidence. The Python reference in [scripts/streaming.py](scripts/streaming.py) has no mandatory third-party imports. Run its behavior tests with Python 3.10 or later:

```sh
python -m unittest discover -s scripts -p 'test_*.py' -v
```

The reference is one request, one candidate, plain text. For tools, structured JSON, resume, cross-provider fallback or multi-candidate responses, define those contracts explicitly at the caller; don't interpret their frames as ordinary text. Set provider read timeouts at the transport and verify the deployed proxy actually flushes. A successful offline suite does not prove streaming in deployment.
