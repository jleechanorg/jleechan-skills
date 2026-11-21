import json
import threading
import unittest
from types import SimpleNamespace as Obj

from streaming import (
    ProviderStreamError, browser_stream, gemini_events, openrouter_events,
    stream_openrouter,
)


def frame(obj):
    return b"data: " + json.dumps(obj, ensure_ascii=False).encode() + b"\r\n\r\n"


def completion(content="", finish=None):
    return {"choices": [{"delta": {"content": content}, "finish_reason": finish}]}


class StreamingTest(unittest.TestCase):
    def test_openrouter_utf8_metadata_and_done(self):
        wire = (b": processing\r\n\r\n"
                + frame(completion("Hi — 🌿"))
                + frame({"choices": [{"delta": {"reasoning": "private"}}]})
                + frame(completion([{"type": "text", "text": " there"},
                                    {"type": "tool_call", "text": "hidden"}], "stop"))
                + frame({"choices": [], "usage": {"total_tokens": 0}})
                + b"data: [DONE]\n\n")
        # Every byte is a separate transport read, including the emoji and CRLF.
        self.assertEqual(list(openrouter_events(bytes([b]) for b in wire)), [
            ("text", "Hi — 🌿"), ("text", " there"),
            ("done", {"finish_reason": "stop", "usage": {"total_tokens": 0}}),
        ])

    def test_openrouter_requires_end_and_does_not_emit_provider_error(self):
        for tail in (b"", frame({"error": {"message": "secret"}}),
                     frame(completion("discard", "error"))):
            with self.subTest(tail=tail):
                it = openrouter_events([frame(completion("partial")), tail])
                self.assertEqual(next(it), ("text", "partial"))
                with self.assertRaises(ProviderStreamError) as cm:
                    list(it)
                self.assertNotIn("secret", str(cm.exception))

    def test_openrouter_multiline_and_truncated_completion(self):
        data = b'data: {"choices":[\ndata: {"delta":{},"finish_reason":"length"}]}\n\ndata: [DONE]\n\n'
        self.assertEqual(list(openrouter_events([data]))[-1],
                         ("done", {"finish_reason": "length", "usage": {}}))

    def test_gemini_yields_visible_parts_then_terminal_data(self):
        chunks = [Obj(candidates=[Obj(content=Obj(parts=[
            Obj(text="visible"), Obj(text="thought", thought=True), Obj(function_call={}),
        ]))]), Obj(candidates=[Obj(finish_reason=Obj(name="STOP"))],
                   usage_metadata=Obj(total_token_count=8, prompt_token_count=0))]
        self.assertEqual(list(gemini_events(chunks)), [
            ("text", "visible"), ("done", {"finish_reason": "STOP",
                                           "usage": {"total_tokens": 8, "prompt_tokens": 0}}),
        ])

    def test_gemini_requires_terminal_and_rejects_prompt_block(self):
        for chunks in ([], [Obj(prompt_feedback=Obj(block_reason=Obj(name="SAFETY")))]):
            with self.subTest(chunks=chunks):
                with self.assertRaises(ProviderStreamError):
                    list(gemini_events(chunks))

    def test_openrouter_transport_contract_and_close(self):
        class Response:
            closed = False

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.closed = True

            def raise_for_status(self):
                pass

            def iter_content(self, *, chunk_size):
                self.chunk_size = chunk_size
                yield frame(completion("first"))
                yield b"data: [DONE]\n\n"

        response = Response()

        def post(url, **kwargs):
            self.assertEqual(url, "https://openrouter.ai/api/v1/chat/completions")
            self.assertTrue(kwargs["stream"])
            self.assertTrue(kwargs["json"]["stream"])
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer fixture")
            self.assertEqual(kwargs["timeout"], (5, 60))
            self.assertFalse(kwargs["allow_redirects"])
            return response

        stream = stream_openrouter(post, "fixture", model="vendor/model", messages=[])
        self.assertEqual(next(stream), ("text", "first"))
        stream.close()
        self.assertTrue(response.closed)

    def test_browser_heartbeat_and_monotonic_visible_events(self):
        release = threading.Event()

        def factory():
            self.assertTrue(release.wait(2))
            yield "text", "a"
            yield "text", "b"
            yield "done", {"finish_reason": "stop", "usage": {}}

        with self.subTest():
            stream = browser_stream(factory, heartbeat=0.01)
            try:
                self.assertEqual(next(stream), b": connected\n\n")
                self.assertEqual(next(stream), b": heartbeat\n\n")
                release.set()
                events = [json.loads(line[6:]) for line in stream if line.startswith(b"data: ")]
                self.assertEqual([e["type"] for e in events], ["chunk", "chunk", "done"])
                self.assertEqual([e["payload"]["sequence"] for e in events[:2]], [0, 1])
            finally:
                release.set()
                stream.close()

    def test_browser_calls_provider_once_and_reports_terminal_failure(self):
        calls, observed_errors = [], []

        def factory():
            calls.append(1)
            yield "text", "partial"
            raise ValueError("secret")

        frames = list(browser_stream(factory, on_error=observed_errors.append))
        events = [json.loads(line[6:]) for line in frames if line.startswith(b"data: ")]
        self.assertEqual(calls, [1])
        self.assertEqual(observed_errors, ["ValueError"])
        self.assertEqual([e["type"] for e in events], ["chunk", "error", "done"])
        self.assertFalse(events[-1]["payload"]["ok"])
        self.assertNotIn(b"secret", b"".join(frames))

    def test_browser_disconnect_closes_iterable_even_when_queue_is_full(self):
        closed = threading.Event()

        def factory():
            try:
                while True:
                    yield "text", "word"
            finally:
                closed.set()

        stream = browser_stream(factory, capacity=1)
        next(stream)
        next(stream)
        stream.close()
        self.assertTrue(closed.wait(1))


if __name__ == "__main__":
    unittest.main()
