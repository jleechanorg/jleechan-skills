import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

SLASH_TOKEN_RE = re.compile(r"(?<![\w/])/([A-Za-z][A-Za-z0-9_-]*)(?![\w/])")
FILE_EXT_RE = re.compile(
    r"\.(sh|md|py|json|jsonl|ya?ml|dot|txt|log|toml|ts|js|html|png|mp4)\b"
)
SKILL_REF_RE = re.compile(r"skills/([A-Za-z0-9_-]+)/SKILL\.md")

NON_COMMAND_TOKENS: dict[str, str] = {
    "tmp": "filesystem path prefix (/tmp/<project-slug>/...), not a command",
    "rate-limit-options": "Claude Code built-in TUI modal, not a repo command",
    "STATE": "mid-path segment from `/tmp/.../STATE.md`, not a command",
    "workflows": "Claude Code built-in Workflow-tool run viewer UI surface, not a repo command file",
    "code": "path fragment from `.../code-quality/`, not a command",
    "config": "path fragment from `~/.claude/teams/session-*/config.json`, not a command",
    "no": "prose false-positive from 'main/no branch', not a command",
    "install": "path fragment of `./install.sh`, not a delegation",
    "reviewer": "slash used as or-separator in `reviewer/subagent` or path segment, not a delegation",
    "pipeline": "Workflow-tool API notation `agent()/parallel()/pipeline()`, not a command",
}


def _get_containing_word(text: str, start: int, end: int) -> str:
    w_start = start
    while w_start > 0 and not text[w_start - 1].isspace():
        w_start -= 1
    w_end = end
    while w_end < len(text) and not text[w_end].isspace():
        w_end += 1
    return text[w_start:w_end]


def extract_references_from_text(text: str) -> set[str]:
    candidates: set[str] = set()

    for match in SLASH_TOKEN_RE.finditer(text):
        word = _get_containing_word(text, match.start(), match.end())

        # R1: word contains a file extension
        # -> real case: .claude/commands/f.md:22 `./install.sh` yields phantom /install
        if FILE_EXT_RE.search(word):
            continue

        # R2: word contains 2 or more "/" characters (path or URL, not a command)
        # -> real case: .claude/commands/f.md:227 `evidence/<run-id>/reviewer-calibration/` yields phantom /reviewer
        if word.count("/") >= 2:
            continue

        # R3: word contains "~/" (home-directory path)
        # -> real case: .claude/commands/zfclevel.md:14 `~/roadmap` yields phantom /roadmap
        if "~/" in word:
            continue

        # R4: word contains "./" or "../" (relative path)
        # -> catches extensionless relative paths (same family as R1)
        if "./" in word or "../" in word:
            continue

        candidates.add(match.group(1))

    # Anchored non-slash reference form: skills/<name>/SKILL.md
    for match in SKILL_REF_RE.finditer(text):
        candidates.add(match.group(1))

    return candidates


def compute_closure(repo_root: Path, seeds: Iterable[str]) -> dict:
    commands_dir = Path(repo_root) / ".claude" / "commands"
    closure: set[str] = set()
    frontier: set[str] = set()
    rejected: dict[str, str] = {}
    edges: dict[str, list[str]] = {}

    for s in seeds:
        if (commands_dir / f"{s}.md").is_file():
            closure.add(s)
            frontier.add(s)
        else:
            rejected[s] = f"no .claude/commands/{s}.md in this repo"

    iterations = 0
    while frontier:
        iterations += 1
        next_frontier: set[str] = set()

        for cmd in sorted(frontier):
            cmd_file = commands_dir / f"{cmd}.md"
            if not cmd_file.is_file():
                continue

            text = cmd_file.read_text(encoding="utf-8")
            raw_candidates = extract_references_from_text(text)

            kept: set[str] = set()
            for cand in sorted(raw_candidates):
                if cand in NON_COMMAND_TOKENS:
                    rejected[cand] = NON_COMMAND_TOKENS[cand]
                elif (commands_dir / f"{cand}.md").is_file():
                    kept.add(cand)
                else:
                    rejected[cand] = f"no .claude/commands/{cand}.md in this repo"

            edges[cmd] = sorted(kept)
            for ref in kept:
                if ref not in closure:
                    closure.add(ref)
                    next_frontier.add(ref)

        frontier = next_frontier

    return {
        "seeds": sorted(set(seeds)),
        "closure": sorted(closure),
        "closure_size": len(closure),
        "edges": {k: edges.get(k, []) for k in sorted(closure)},
        "rejected": {k: rejected[k] for k in sorted(rejected)},
        "iterations": iterations,
    }


def closure_to_json(result: dict) -> str:
    return json.dumps(result, indent=2, sort_keys=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute fixed-point command dependency closure."
    )
    parser.add_argument(
        "--seed",
        nargs="+",
        metavar="NAME",
        help="Explicit seed command names.",
    )
    parser.add_argument(
        "--seed-from",
        type=str,
        metavar="PATH",
        help="Path to snapshot JSON produced by rank_commands_repo_scoped.py",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output full closure as deterministic JSON.",
    )
    args = parser.parse_args()

    if not args.seed and not args.seed_from:
        parser.error("Must provide either --seed or --seed-from.")

    seeds: list[str] = []
    if args.seed:
        seeds.extend(args.seed)
    if args.seed_from:
        seed_path = Path(args.seed_from)
        if not seed_path.is_file():
            sys.exit(f"Error: seed file not found: {seed_path}")
        with open(seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "union" in data and isinstance(data["union"], list):
            seeds.extend(data["union"])
        else:
            top_human = data.get("top20_human", [])
            top_agent = data.get("top20_agent", [])
            seen: set[str] = set()
            for s in top_human + top_agent:
                if s not in seen:
                    seen.add(s)
                    seeds.append(s)

    repo_root = Path(__file__).resolve().parent.parent
    result = compute_closure(repo_root, seeds)

    if args.json_output:
        print(closure_to_json(result))
    else:
        print(f"Seeds: {len(result['seeds'])}")
        print(f"Closure size: {result['closure_size']}")
        print(f"Iterations: {result['iterations']}")
        print("Closure:")
        for name in result["closure"]:
            print(f"  /{name}")


if __name__ == "__main__":
    main()
