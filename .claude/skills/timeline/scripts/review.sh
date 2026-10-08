#!/usr/bin/env bash
# Render a timeline HTML in a real browser and save a full-page PNG next to it.
# Prefers headless Google Chrome; falls back to Aside (account u0).
# Prints the PNG path. Usage: review.sh <file.html> [height_px]
set -uo pipefail
[ -f "${1:-}" ] || { echo "review.sh: usage: review.sh <file.html> [height_px]" >&2; exit 1; }
dir="$(cd "$(dirname "$1")" && pwd)"; name="$(basename "$1")"
html="$dir/$name"; png="$dir/${name%.html}.png"; height="${2:-1100}"
rm -f "$png"

chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$chrome" ] || chrome="$(command -v google-chrome || command -v chromium || true)"
if [ -n "$chrome" ]; then
  timeout 60 "$chrome" --headless=new --disable-gpu --hide-scrollbars \
    --window-size=1200,"$height" --screenshot="$png" "file://$html" >/dev/null 2>&1
  [ -s "$png" ] && { echo "$png"; exit 0; }
  echo "review.sh: headless Chrome failed; trying Aside" >&2
fi

command -v aside >/dev/null || { echo "review.sh: no Chrome and no aside CLI" >&2; exit 2; }
# Aside cannot open file:// URLs, so serve the directory on a free loopback port.
port=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
python3 -m http.server "$port" --bind 127.0.0.1 --directory "$dir" >/dev/null 2>&1 &
srv=$!; trap 'kill $srv 2>/dev/null' EXIT; sleep 1
url=$(python3 -c 'import json,sys,urllib.parse;print(json.dumps("http://127.0.0.1:%s/%s"%(sys.argv[1],urllib.parse.quote(sys.argv[2]))))' "$port" "$name")
# Aside sandboxes screenshot paths into its session tmp dir and prints "Saved it to <path>";
# its repl exits 0 even on a JS error, so check the output for "[error".
out=$(timeout 100 aside repl --account "${ASIDE_ACCOUNT:-u0}" "
const p = await openTab($url);
await new Promise(r => setTimeout(r, 800));
await p.screenshot({path: 'timeline.png', fullPage: true});
await p.close();
" 2>&1)
case "$out" in *"[error"*) echo "$out" >&2; exit 3;; esac
saved=$(printf '%s\n' "$out" | sed -n 's/.*Saved it to \(.*\.png\).*/\1/p' | tail -1)
[ -s "$saved" ] || { echo "$out" >&2; echo "review.sh: screenshot not found" >&2; exit 4; }
cp "$saved" "$png" && echo "$png"
