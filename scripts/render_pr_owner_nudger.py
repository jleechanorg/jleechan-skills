#!/usr/bin/env python3
"""Render a scheduler package in an explicitly selected staging directory."""

import argparse
import plistlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAME = "pr-owner-nudger"


def lane_targets(name):
    """Validate a scheduler lane name and return (launchd_label, systemd_service)."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name.startswith("."):
        raise ValueError("--name may contain only letters, digits, dot, underscore and hyphen")
    return f"org.prw.{name}", f"{name}.service"


def quote_systemd_path(path):
    escapes = str.maketrans({"\\": "\\\\", '"': '\\"', "%": "%%", "$": "$$",
                             "\n": "\\n", "\r": "\\r"})
    return '"' + str(path).translate(escapes) + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scheduler", choices=("launchd", "systemd"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="enable dispatch in the unit")
    parser.add_argument("--name", default=DEFAULT_NAME,
                        help="unit/label name, for a second lane with its own config and state")
    args = parser.parse_args()
    try:
        label, _ = lane_targets(args.name)
    except ValueError as exc:
        parser.error(str(exc))
    name = args.name

    config = args.config.expanduser().absolute()
    wrapper = ROOT / "scripts" / "run_pr_owner_nudger.sh"
    args.output.mkdir(parents=True, exist_ok=True)
    if args.scheduler == "launchd":
        filename = f"{label}.plist"
        with (ROOT / "launchd" / f"org.prw.{DEFAULT_NAME}.plist.template").open("rb") as template:
            job = plistlib.load(template)
        job["Label"] = label
        job["ProgramArguments"].extend([str(wrapper), "--config", str(config)])
        if args.apply:
            job["ProgramArguments"].append("--apply")
        for key in ("StandardOutPath", "StandardErrorPath"):
            job[key] = job[key].replace("@HOME@", str(Path.home())).replace(DEFAULT_NAME, name)
        with (args.output / filename).open("wb") as output:
            plistlib.dump(job, output)
        return

    for suffix in ("service", "timer"):
        filename = f"{DEFAULT_NAME}.{suffix}"
        template = (ROOT / "systemd" / f"{filename}.template").read_text()
        job = template.replace(DEFAULT_NAME, name).format(
            wrapper=quote_systemd_path(wrapper),
            config=quote_systemd_path(config),
            apply=" --apply" if args.apply else "",
        )
        (args.output / f"{name}.{suffix}").write_text(job)


if __name__ == "__main__":
    main()
