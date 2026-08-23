#!/usr/bin/env python3
"""Codex SessionStart hook: inject relevant mem0 + Claude auto-memories before session starts.

Two sources:
  1. Claude file-based auto-memories (~/.claude/projects/*/memory/MEMORY.md)
  2. mem0 Qdrant vector store (semantic search via local Ollama embeddings)

Output format: {"context": "..."} or {"continue": true}
Silently falls back to {"continue": true} on any error.
"""
from __future__ import annotations

import json
import os
import subprocess
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

TOP_K = 6
SCORE_THRESHOLD = 0.35
USER_ID = "$USER"

FALLBACK = json.dumps({"continue": True})


def _read_claude_memories() -> str:
    """Read Claude file-based auto-memories for the current project.

    Finds ~/.claude/projects/{git-root-as-key}/memory/MEMORY.md and returns
    the index content (trimmed). Falls back to empty string on any error.
    """
    try:
        git_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        project_key = git_root.replace("/", "-")  # /Users/foo → -Users-foo
        memory_dir = os.path.expanduser(f"~/.claude/projects/{project_key}/memory")
        index_path = os.path.join(memory_dir, "MEMORY.md")
        if not os.path.exists(index_path):
            return ""
        content = open(index_path).read().strip()
        if not content:
            return ""
        # Trim to last 30 bullet entries + any header lines
        lines = content.splitlines()
        header_lines = [l for l in lines if not l.startswith("-")][:5]
        entry_lines = [l for l in lines if l.startswith("-")][-30:]
        trimmed = "\n".join(header_lines + entry_lines)
        return f"## Claude project memories (index)\n{trimmed}"
    except Exception:
        return ""


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        print(FALLBACK)
        sys.exit(0)

    # Extract query — try common fields
    query = (
        data.get("task")
        or data.get("prompt")
        or data.get("message")
        or data.get("userMessage")
        or ""
    ).strip()

    # Skip short queries and slash commands (fast path — no Qdrant/Ollama cost)
    if not query or len(query) < 20:
        print(FALLBACK)
        sys.exit(0)
    if query.startswith("/"):
        print(FALLBACK)
        sys.exit(0)

    sections: list[str] = []

    # Source 1: Claude auto-memories (fast — file read, no network)
    claude_mems = _read_claude_memories()
    if claude_mems:
        sections.append(claude_mems)

    # Source 2: mem0 Qdrant semantic search (local Ollama embedder + LLM)
    try:
        from mem0 import Memory  # type: ignore

        m = Memory.from_config(MEM0_CONFIG)
        raw = m.search(query, user_id=USER_ID, limit=TOP_K)
        results = raw.get("results", raw) if isinstance(raw, dict) else raw

        hits = [
            r for r in results
            if isinstance(r.get("score"), (int, float)) and r["score"] >= SCORE_THRESHOLD
        ]

        if hits:
            lines = ["## Relevant memories (from past sessions)"]
            for r in hits:
                mem = r.get("memory", r.get("data", "")).strip()
                score = r.get("score", 0)
                if mem:
                    lines.append(f"- [{score:.2f}] {mem}")
            sections.append("\n".join(lines))
    except Exception:
        pass  # mem0 unavailable — Claude memories still injected if present

    if not sections:
        print(FALLBACK)
        sys.exit(0)

    context = "\n\n".join(sections)
    print(json.dumps({"context": context}))
    sys.exit(0)


if __name__ == "__main__":
    main()
