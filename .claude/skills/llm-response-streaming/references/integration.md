# Integration guide

## Install only what you use

Use Python 3.10+. The parser and relay have no third-party dependencies.
Install your selected dependencies in the application's virtual environment:

```sh
python -m pip install google-genai  # Gemini direct
python -m pip install requests     # OpenRouter
python -m pip install Flask        # only for the server example below
```

Pin only the dependencies you use in your lockfile. Copy `scripts/streaming.py` into your application beside the integration module, or add the skill's `scripts/` directory to your application import path. Load keys through your application's secret configuration, never the browser.

```python
# Available when the skill's scripts directory is on sys.path.
from streaming import browser_stream, stream_gemini, stream_openrouter

# Gemini direct (google-genai): not the Gemini Interactions API.
gemini = lambda: stream_gemini(
    gemini_client, model=gemini_model, contents=prompt,
)
# OpenRouter (/api/v1/chat/completions): not the Responses API.
from requests import post
openrouter = lambda: stream_openrouter(
    post, openrouter_key, model=openrouter_model,
    messages=[{"role": "user", "content": prompt}],
)
```

Select one factory after validating and authorizing the request. Capture request inputs before handing off to the worker thread; do not rely on request-local globals there.

```python
from flask import Response, stream_with_context

def sse_reply(factory):
    return Response(
        stream_with_context(browser_stream(factory)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
```

Use this with a prevalidated request; authentication, request limits, model selection and credential ownership belong in the caller. Put an end-to-end deadline and a concurrency limit around production streams. The sample's heartbeat is a downstream keep-alive, not an upstream timeout. A disconnected client cannot interrupt a blocked synchronous read; the relay can close the iterator when the adapter next yields, completes, or times out. Configure provider read/total deadlines. Cancellation is best-effort and does not guarantee the provider stops billing.

## Event contract

Transport uses default SSE messages with JSON `{type, payload}`. The opening and heartbeat comments are ignored by browser SSE listeners.

- `chunk`: `payload.sequence` (zero-based, monotonically increasing), `payload.text` (appendable text).
- `done`: `payload.ok` describes stream transport success. On success also carries the provider's `finish_reason` and any available `usage`. `length` and `MAX_TOKENS` mean truncated, not a finished answer. Safety or content-filter finish reasons need corresponding UI treatment. Unknown or absent usage is not zero.
- `error` then unsuccessful `done`: Stable code only. Keep the visible prefix and show interruption. A missing terminal event likewise indicates an interrupted transport, not a complete answer. Pass `on_error=record_error_kind` to receive the exception class name for server-side metrics. The reference never forwards raw error messages. For richer diagnostics, record scrubbed details inside your own provider factory before reraising.

A same-origin GET can use `EventSource` if the endpoint is safe to reconnect. Turn off automatic reconnect on both terminal event and interruption. For POST, use `fetch` with an incremental SSE parser that holds a streaming `TextDecoder`, or a maintained SSE client. Do not parse one network packet as one JSON object. Render user/model text with DOM text APIs, not raw HTML.

## Provider differences

- [Gemini GenerateContent API](https://aistudio.google.com/api-reference/generate-content): use `client.models.generate_content_stream`, inspect candidate parts, skip explicit thought and non-text parts, and merge usage/finish metadata even when no visible text is present.
- [OpenRouter Chat Completions streaming](https://openrouter.ai/docs/api_reference/streaming#chat-completions): check HTTP status before reading, join byte fragments before strict UTF-8 decoding, and parse complete `data:` events. Comments are keep-alives, empty choices can carry usage, and HTTP 200 can still contain an error frame. Expect `[DONE]`; a socket close without it is not success. This reference supports LF and CRLF framing and fields split across reads.
- No implicit retry. If application policy allows fallback, it must happen before the first visible chunk, with a bounded budget. After output, end with a terminal failure; a deliberate new attempt is a distinct request.

## Prove delivery

Run the unit suite on synthetic provider chunks first. Then, if authorized, run an integration check through the intended HTTP route and proxy, with an intentionally delayed first provider chunk and at least two separated text chunks. Observe the opening comment before the provider returns, a heartbeat during a pause, visible chunks at distinct read times, then terminal metadata. Compare timestamped provider and consumer sequence numbers under one request ID; separately check cancellation and failure after partial output. Disable buffering/compression for the route where required. A fully buffered response can pass a final-text test.
