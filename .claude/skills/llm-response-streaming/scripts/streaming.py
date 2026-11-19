"""Text-only provider adapters and a synchronous browser SSE relay."""
import json
from queue import Empty, Full, Queue
from threading import Event, Thread


class ProviderStreamError(RuntimeError):
    pass


def _sse_data(chunks):
    """Split on LF after joining bytes; CRLF and multiline data are supported."""
    buffer = bytearray()
    data = []
    for chunk in chunks:
        buffer.extend(chunk)
        while (end := buffer.find(b"\n")) >= 0:
            line = bytes(buffer[:end]).removesuffix(b"\r")
            del buffer[:end + 1]
            if not line:
                if data:
                    yield b"\n".join(data).decode("utf-8")
                    data.clear()
            elif line.startswith(b"data:"):
                data.append(line[5:].removeprefix(b" "))
    # An incomplete event is not success; the provider adapter requires [DONE].


def openrouter_events(chunks):
    usage, reason = {}, None
    for data in _sse_data(chunks):
        if data == "[DONE]":
            yield "done", {"finish_reason": reason, "usage": usage}
            return
        frame = json.loads(data)
        choice = (frame.get("choices") or [{}])[0]
        if frame.get("error") or choice.get("finish_reason") == "error":
            raise ProviderStreamError("OpenRouter reported a stream error")
        if choice.get("finish_reason"):
            reason = choice["finish_reason"]
        usage.update({k: v for k, v in (frame.get("usage") or {}).items() if v is not None})
        content = (choice.get("delta") or {}).get("content")
        if isinstance(content, str) and content:
            yield "text", content
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str) and text:
                        yield "text", text
    raise ProviderStreamError("OpenRouter stream ended without [DONE]")


def stream_openrouter(post, api_key, *, model, messages, timeout=(5, 60)):
    """Pass requests.Session().post or a compatible callable."""
    with post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "text/event-stream"},
        json={"model": model, "messages": messages, "stream": True},
        stream=True, timeout=timeout, allow_redirects=False,
    ) as response:
        response.raise_for_status()
        if getattr(response, "status_code", 200) != 200:
            raise ProviderStreamError("OpenRouter did not return an SSE response")
        yield from openrouter_events(response.iter_content(chunk_size=128))


def _name(value):
    return (getattr(value, "name", value) or "").rsplit(".", 1)[-1]


def gemini_events(chunks):
    reason, usage = None, {}
    fields = {
        "prompt_token_count": "prompt_tokens",
        "candidates_token_count": "completion_tokens",
        "total_token_count": "total_tokens",
        "cached_content_token_count": "cached_input_tokens",
    }
    for chunk in chunks:
        feedback = getattr(chunk, "prompt_feedback", None)
        if _name(getattr(feedback, "block_reason", None)) not in ("", "BLOCK_REASON_UNSPECIFIED"):
            raise ProviderStreamError("Gemini blocked the request")
        metadata = getattr(chunk, "usage_metadata", None)
        for field, key in fields.items():
            value = getattr(metadata, field, None)
            if value is not None:
                usage[key] = value
        candidates = getattr(chunk, "candidates", None) or ()
        if not candidates:
            continue
        candidate = candidates[0]
        finish = _name(getattr(candidate, "finish_reason", None))
        if finish not in ("", "FINISH_REASON_UNSPECIFIED"):
            reason = finish
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or ():
            text = getattr(part, "text", None)
            if isinstance(text, str) and text and not getattr(part, "thought", False):
                yield "text", text
    if reason is None:
        raise ProviderStreamError("Gemini stream ended without a finish reason")
    yield "done", {"finish_reason": reason, "usage": usage}


def stream_gemini(client, *, model, contents, config=None):
    """Pass a configured google.genai.Client; it owns credentials and timeout."""
    chunks = client.models.generate_content_stream(model=model, contents=contents, config=config)
    try:
        yield from gemini_events(chunks)
    finally:
        if (close := getattr(chunks, "close", None)) is not None:
            close()


def _frame(kind, payload):
    return ("data: " + json.dumps({"type": kind, "payload": payload}, ensure_ascii=False) + "\n\n").encode()


def browser_stream(factory, *, heartbeat=15, capacity=32, on_error=None):
    """Relay one lazy provider stream; never restart a partially emitted reply."""
    if heartbeat <= 0 or capacity < 1:
        raise ValueError("heartbeat and capacity must be positive")
    messages, stop = Queue(capacity), Event()

    def put(message):
        while not stop.is_set():
            try:
                messages.put(message, timeout=0.05)
                return True
            except Full:
                pass
        return False

    def report_error(error):
        if on_error is not None:
            try:
                on_error(type(error).__name__)
            except Exception:
                # Observer failure must not prevent delivering terminal status.
                pass

    def produce():
        upstream = None
        terminal = ("failed", None)
        try:
            upstream = iter(factory())
            for kind, value in upstream:
                if kind == "done":
                    terminal = ("done", value)
                    break
                if kind == "text" and not put((kind, value)):
                    return
        except Exception as error:
            report_error(error)
        finally:
            if (close := getattr(upstream, "close", None)) is not None:
                try:
                    close()
                except Exception as error:
                    report_error(error)
                    terminal = ("failed", None)
            put(terminal)

    yield b": connected\n\n"
    worker = Thread(target=produce, daemon=True)
    worker.start()
    try:
        sequence = 0
        while True:
            try:
                kind, value = messages.get(timeout=heartbeat)
            except Empty:
                yield b": heartbeat\n\n"
                continue
            if kind == "text":
                yield _frame("chunk", {"sequence": sequence, "text": value})
                sequence += 1
            elif kind == "done":
                yield _frame("done", {**value, "ok": True})
                return
            else:
                yield _frame("error", {"code": "provider_stream_failed"})
                yield _frame("done", {"ok": False})
                return
    finally:
        stop.set()
