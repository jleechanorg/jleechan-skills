import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

LIVE_SCANNER = os.path.expanduser(
    "~/.claude/skills/command-research/scripts/count_command_usage_unified.py"
)


def load_payload(input_path=None):
    if input_path:
        with open(input_path, "r", encoding="utf-8") as f:
            return json.load(f)
    proc = subprocess.run(
        [sys.executable, LIVE_SCANNER, "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def rank_commands(payload, repo_root):
    commands_dir = repo_root / ".claude" / "commands"

    def top20(mapping):
        filtered = {
            k: v
            for k, v in mapping.items()
            if (commands_dir / f"{k}.md").is_file()
        }
        sorted_keys = sorted(filtered.keys(), key=lambda k: (-filtered[k], k))
        return sorted_keys[:20]

    top20_human = top20(payload.get("human", {}))
    top20_agent = top20(payload.get("agent", {}))

    union = []
    seen = set()
    for cmd in top20_human + top20_agent:
        if cmd not in seen:
            seen.add(cmd)
            union.append(cmd)

    return {
        "top20_human": top20_human,
        "top20_agent": top20_agent,
        "union": union,
    }


def main():
    parser = argparse.ArgumentParser(description="Rank repo-scoped commands by usage.")
    parser.add_argument("--input", type=str, help="Path to input snapshot JSON")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    payload = load_payload(args.input)
    result = rank_commands(payload, repo_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
