#!/usr/bin/env python3
"""Codex Stop hook: extract facts from the last turn and save to mem0.

Called from stop-hook-dispatch.sh after Codex finishes a turn.
Reads the stop payload from stdin, extracts the assistant message,
and uses mem0 LLM extraction to distill and save facts to qdrant.

Always returns {"continue": true} — never blocks Codex.
"""
from __future__ import annotations

import json
import os
import sys

MEM0_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "127.0.0.1",
            "port": 6333,
            "collection_name": "openclaw_mem0",
            "embedding_model_dims": 768,
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434",
        },
    },
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "llama3.2:3b",
            "ollama_base_url": "http://localhost:11434",
        },
    },
    "version": "v1.1",
}

USER_ID = "$USER"
MIN_LENGTH = 100

CONTINUE = json.dumps({"continue": True})


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        print(CONTINUE)
        sys.exit(0)

    # Extract assistant message — try common Codex stop payload fields
    message = (
        data.get("lastAssistantMessage")
        or data.get("last_assistant_message")
        or data.get("assistantMessage")
        or data.get("message")
        or ""
    ).strip()

    if len(message) < MIN_LENGTH:
        print(CONTINUE)
        sys.exit(0)

    # Skip pure code blocks (heuristic)
    if message.count(". ") < 2 and message.count("\n") > 20:
        print(CONTINUE)
        sys.exit(0)

    try:
        from mem0 import Memory  # type: ignore

        m = Memory.from_config(MEM0_CONFIG)
        m.add(message, user_id=USER_ID, infer=True)
    except Exception:
        pass

    print(CONTINUE)
    sys.exit(0)


if __name__ == "__main__":
    main()
