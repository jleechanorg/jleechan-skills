#!/usr/bin/env python3
"""Resolve an install profile from shared/install-profiles.json into installer entries.

Each output line is a component-relative path the installer may copy:
skills/<name>, commands/<file>.md, agents/<file>.md, scripts/<entry> or
extra/<file> (a repository-level scripts/ file installed into scripts/).
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROFILES_FILE = Path("shared/install-profiles.json")
SKILL_LINK = re.compile(r"(?:\.\./|skills/)([A-Za-z0-9_.-]+)/")
COMMAND_TARGET = re.compile(r"skills/([A-Za-z0-9_.-]+)/SKILL\.md")
COMMAND_COMPANION = re.compile(r"commands/([A-Za-z0-9_./-]+)")
SCRIPT_LINK = re.compile(r"(?:\.claude|CLAUDE_HOME\}?|claude)/scripts/([A-Za-z0-9_.-]+)")
AGENT_LINKS = (
    re.compile(r"agents/([A-Za-z0-9_.-]+)\.md"),
    re.compile(r"`([A-Za-z0-9_.-]+)`\s+(?:sub)?agent"),
    re.compile(r"subagent_type\W{1,4}([A-Za-z0-9_.-]+)"),
)
EXTRAS = ("history_search.py", "integrate.sh")
ALIAS_MAX_LINES = 15
SKIPPED_PARTS = {"__pycache__", ".pytest_cache", "_archive"}


class ProfileError(Exception):
    pass


def load(source):
    path = source / PROFILES_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProfileError(f"Cannot read install profiles {path}: {error}") from error
    def string_list(value):
        return isinstance(value, list) and all(isinstance(item, str) and item for item in value)

    # A wrong type must fail closed: a denylist string would otherwise iterate as letters.
    profiles = data.get("profiles") if isinstance(data, dict) else None
    problems = []
    if not isinstance(profiles, dict) or data.get("default_profile") not in profiles:
        problems.append("profiles/default_profile")
    else:
        for name, spec in profiles.items():
            if not isinstance(spec, dict):
                problems.append(f"profiles.{name}")
                continue
            problems += [f"profiles.{name}.{field}" for field in ("skills", "commands", "include")
                         if field in spec and not string_list(spec[field])]
    # closure_excluded is safety metadata, so an omitted or empty list fails closed
    # instead of silently installing the cookie- and personal-infra skills.
    excluded = data.get("closure_excluded") if isinstance(data, dict) else None
    if not string_list(excluded) or not excluded:
        problems.append("closure_excluded (required non-empty list of names)")
    if problems:
        raise ProfileError(f"Malformed install profiles {path}: {', '.join(problems)} must be a list of names")
    return data


def read_texts(path):
    """Yield the text of every installable file under path (or path itself)."""
    files = [path] if path.is_file() else sorted(path.rglob("*"))
    for item in files:
        parts = set(item.parts)
        if not item.is_file() or SKIPPED_PARTS & parts or any(p.startswith("_archived_") for p in item.parts):
            continue
        try:
            yield item.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def is_alias(path, text, skill):
    """A command aliases skill when its stem names it, its description says alias, or it is <= 15 lines."""
    description = ""
    if text.startswith("---\n"):
        front = text[4:].split("\n---", 1)[0]
        description = next((line for line in front.splitlines() if line.startswith("description:")), "")
    return path.stem == skill or "alias" in description.lower() or len(text.splitlines()) <= ALIAS_MAX_LINES


def seeds_for(data, name, seen=()):
    if name not in data["profiles"]:
        raise ProfileError(f"Unknown install profile: {name} (available: {', '.join(data['profiles'])})")
    if name in seen:
        raise ProfileError(f"Install profile include cycle at: {name}")
    spec = data["profiles"][name]
    skills, commands = list(spec.get("skills", [])), list(spec.get("commands", []))
    for included in spec.get("include", []):
        more_skills, more_commands = seeds_for(data, included, (*seen, name))
        skills += more_skills
        commands += more_commands
    return skills, commands


def resolve(source, name, extra_skills=()):
    data = load(source)
    claude = source / ".claude"
    skills_root, commands_root = claude / "skills", claude / "commands"
    available = {
        p.name for p in skills_root.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file() and not p.name.startswith("_")
    } if skills_root.is_dir() else set()
    seed_skills, seed_commands = seeds_for(data, name)
    seed_skills += list(extra_skills)
    excluded = set(data.get("closure_excluded", []))

    explicit_commands = []
    named_skills = set(seed_skills)
    for command in seed_commands:
        for candidate in (f"{command}.md", f"extended-library/{command}.md"):
            if (commands_root / candidate).is_file():
                explicit_commands.append(candidate)
                target = COMMAND_TARGET.search((commands_root / candidate).read_text(encoding="utf-8"))
                if target:
                    # A command whose own target skill is absent would install a
                    # pointer to nothing, so refuse it before any write.
                    if target.group(1) not in available:
                        raise ProfileError(
                            f"Profile {name} command {command} targets missing skill {target.group(1)}")
                    if target.group(1) in excluded and target.group(1) not in named_skills:
                        raise ProfileError(
                            f"Profile {name} command {command} targets closure-excluded skill "
                            f"{target.group(1)}; name it in the profile's skills or pass --with")
                    seed_skills.append(target.group(1))
                break
        else:
            raise ProfileError(f"Profile {name} names a missing command: {command}")
    missing = sorted(set(seed_skills) - available)
    if missing:
        raise ProfileError(f"Profile {name} names missing skills: {', '.join(missing)}")

    # Closure never adds an excluded skill; only a profile entry or --with does.
    seeds = set(seed_skills)
    skills, stack = set(seeds), sorted(seeds)
    while stack:
        current = stack.pop()
        for text in read_texts(skills_root / current):
            for linked in SKILL_LINK.findall(text):
                if linked in available and linked not in skills and (linked not in excluded or linked in seeds):
                    skills.add(linked)
                    stack.append(linked)

    # Aliases follow seeds only; a skill that arrived by closure brings no slash
    # commands, and a long workflow that merely cites a seed is not its alias.
    commands = set(explicit_commands)
    if commands_root.is_dir():
        for path in [*commands_root.glob("*.md"), *(commands_root / "extended-library").glob("*.md")]:
            text = path.read_text(encoding="utf-8", errors="replace")
            target = COMMAND_TARGET.search(text)
            if target and target.group(1) in seeds and is_alias(path, text, target.group(1)):
                commands.add(path.relative_to(commands_root).as_posix())
    # A selected command's referenced non-Markdown helper under commands/ installs with it.
    for command in sorted(commands):
        for reference in COMMAND_COMPANION.findall((commands_root / command).read_text(encoding="utf-8", errors="replace")):
            reference = reference.rstrip(".")
            if (not reference.endswith(".md") and ".." not in reference.split("/")
                    and (commands_root / reference).is_file()):
                commands.add(reference)

    texts = [t for s in sorted(skills) for t in read_texts(skills_root / s)]
    texts += [t for c in sorted(commands) for t in read_texts(commands_root / c)]
    agents_root, scripts_root = claude / "agents", claude / "scripts"
    agent_names = {p.stem for p in agents_root.glob("*.md")} if agents_root.is_dir() else set()
    agents = {m for t in texts for pattern in AGENT_LINKS for m in pattern.findall(t) if m in agent_names}
    texts += [t for a in sorted(agents) for t in read_texts(agents_root / f"{a}.md")]

    script_names = {p.name for p in scripts_root.iterdir()} if scripts_root.is_dir() else set()
    scripts, pending = set(), list(texts)
    while pending:
        for linked in SCRIPT_LINK.findall(pending.pop()):
            if linked in script_names and linked not in scripts:
                scripts.add(linked)
                pending.extend(read_texts(scripts_root / linked))
    extras = {e for e in EXTRAS if (source / "scripts" / e).is_file() and any(e in t for t in texts)}

    return (
        [f"skills/{s}" for s in sorted(skills)]
        + [f"commands/{c}" for c in sorted(commands)]
        + [f"agents/{a}.md" for a in sorted(agents)]
        + [f"scripts/{s}" for s in sorted(scripts)]
        + [f"extra/{e}" for e in sorted(extras)]
    )


def describe(source):
    data = load(source)
    lines = []
    for name, spec in data["profiles"].items():
        marker = " (default)" if name == data["default_profile"] else ""
        lines.append(f"  {name}{marker}\n      {spec.get('description', '')}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--resolve", metavar="PROFILE")
    group.add_argument("--default", action="store_true")
    group.add_argument("--list", action="store_true")
    parser.add_argument("--with", dest="extra", action="append", default=[], metavar="SKILL",
                        help="add a skill to the profile seeds, including a closure-excluded one")
    args = parser.parse_args(argv)
    try:
        if args.list:
            print(describe(args.source))
        elif args.default:
            print(load(args.source)["default_profile"])
        else:
            print("\n".join(resolve(args.source, args.resolve, args.extra)))
    except ProfileError as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
