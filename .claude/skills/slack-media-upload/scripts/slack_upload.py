#!/usr/bin/env python3
"""Upload local files to Slack as native inline attachments.

No Slack MCP server currently ships a working files.upload tool (verified
2026-09-01 against korotovsky/slack-mcp-server v1.2.2/v1.3.0 and every
alternative surveyed — see
docs/research/2026-09-01-slack-mcp-file-upload-support.md in worldarchitect.ai).
This wraps Slack's own current-recommended flow directly:
files.getUploadURLExternal -> PUT bytes -> files.completeUploadExternal.

Usage:
  slack_upload.py --channel C09GRLXF9GR --file a.png --file b.mp4 \
      --title "Before" --title "After" --comment "evidence" \
      [--thread-ts 1234567890.123456]

  slack_upload.py --dm --file a.png --comment "for you"
"""
import argparse
import os
import sys

import requests

API = "https://slack.com/api"


def resolve_token() -> str:
    """SLACK_BOT_TOKEN first — it is the token verified to carry files:write.

    korotovsky/slack-mcp-server silently prefers SLACK_MCP_XOXP_TOKEN (user
    token) over SLACK_MCP_XOXB_TOKEN whenever both are set, and the user
    token has historically lacked files:write (see files-write-scope-reinstall
    incident, 2026-07-19). This script never reads that MCP-server pair —
    it reads SLACK_BOT_TOKEN directly so it can't inherit that gap.
    """
    token = os.environ.get("SLACK_BOT_TOKEN") or os.environ.get("HERMES_SLACK_BOT_TOKEN")
    if not token:
        sys.exit("SLACK_BOT_TOKEN (or HERMES_SLACK_BOT_TOKEN) not set in environment")
    return token


def resolve_channel(args) -> str:
    if args.channel:
        return args.channel
    if args.dm:
        dm = os.environ.get("JLEECHAN_DM_CHANNEL")
        if not dm:
            sys.exit("--dm requested but JLEECHAN_DM_CHANNEL is not set")
        return dm
    sys.exit("Provide --channel <id> or --dm")


def api_post(token: str, method: str, **payload):
    resp = requests.post(
        f"{API}/{method}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        sys.exit(f"{method} failed: {data}")
    return data


def upload_one(token: str, path: str, title: str) -> dict:
    size = os.path.getsize(path)
    name = os.path.basename(path)
    step1 = requests.post(
        f"{API}/files.getUploadURLExternal",
        headers={"Authorization": f"Bearer {token}"},
        data={"filename": name, "length": size},
        timeout=30,
    ).json()
    if not step1.get("ok"):
        sys.exit(f"files.getUploadURLExternal failed for {name}: {step1}")

    with open(path, "rb") as f:
        put_resp = requests.post(step1["upload_url"], files={"file": f}, timeout=120)
    if put_resp.status_code != 200:
        sys.exit(f"upload PUT failed for {name}: HTTP {put_resp.status_code} {put_resp.text[:200]}")

    return {"id": step1["file_id"], "title": title or name}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file", action="append", required=True, help="Local file path; repeatable")
    p.add_argument("--title", action="append", default=[], help="Title per --file, same order; repeatable")
    p.add_argument("--channel", help="Slack channel ID (Cxxxx)")
    p.add_argument("--dm", action="store_true", help="Send to $JLEECHAN_DM_CHANNEL instead of --channel")
    p.add_argument("--thread-ts", help="Reply in this thread instead of posting a new top-level message")
    p.add_argument("--comment", default="", help="initial_comment posted with the files")
    args = p.parse_args()

    if args.title and len(args.title) != len(args.file):
        sys.exit("--title count must match --file count (or omit --title entirely)")

    token = resolve_token()
    channel = resolve_channel(args)

    files_payload = []
    for i, path in enumerate(args.file):
        if not os.path.isfile(path):
            sys.exit(f"not a file: {path}")
        title = args.title[i] if args.title else os.path.basename(path)
        print(f"uploading {path} ...", file=sys.stderr)
        files_payload.append(upload_one(token, path, title))

    complete_payload = {
        "files": files_payload,
        "channel_id": channel,
        "initial_comment": args.comment,
    }
    if args.thread_ts:
        complete_payload["thread_ts"] = args.thread_ts

    result = api_post(token, "files.completeUploadExternal", **complete_payload)
    posted_ts = None
    for f in result.get("files", []):
        shares = f.get("shares", {})
        for visibility in ("public", "private"):
            for msgs in shares.get(visibility, {}).values():
                for m in msgs:
                    posted_ts = m.get("ts")
    print(f"OK: {len(files_payload)} file(s) posted to {channel}" + (f" (ts={posted_ts})" if posted_ts else ""))


if __name__ == "__main__":
    main()
