#!/bin/bash
# Read-only. Print absolute paths under ROOTS that are older than MIN minutes (default 360 = 6h),
# have no open file beneath them, and are not state-like. Writes the open-file list to $OPEN_LIST.
#   ROOTS="/private/tmp:/path/to/scratch" OPEN_LIST=/path/open.txt [MIN=360] [DEPTH=1|2] [P=8] qualify.sh > candidates.txt
# DEPTH=2 also returns old children of directories that are partly active (children whose parent is
# already a candidate are dropped, since deleting the parent covers them).
set -u
: "${ROOTS:?colon-separated absolute roots}"
: "${OPEN_LIST:?path to write the open-file list}"
MIN="${MIN:-360}"; DEPTH="${DEPTH:-1}"; P="${P:-8}"
IFS=: read -r -a RS <<< "$ROOTS"

ALL=$(mktemp); OLD=$(mktemp); CAND=$(mktemp)
trap 'rm -f "$ALL" "$OLD" "$CAND"' EXIT

for r in "${RS[@]}"; do
  case "$r" in /?*) ;; *) echo "bad root: $r" >&2; exit 2;; esac
  [ -d "$r" ] || { echo "missing root: $r" >&2; exit 2; }
  find "$r" -mindepth 1 -maxdepth "$DEPTH" -user "$(id -un)" \( -type f -o -type d -o -type l \) ! -name '.*' ! -path "$r/.*" ! -path "$r/*/.*" -print0
done > "$ALL"

# 1. age: nothing modified or status-changed beneath the entry within MIN minutes
export MIN CTIME="${CTIME:-1}"   # CTIME=0 is for fixtures only: ctime cannot be back-dated
xargs -0 -n1 -P"$P" bash -c '
  p="$1"
  if [ "$CTIME" = 0 ]; then n=$(find "$p" -mmin -"$MIN" -print -quit 2>/dev/null)
  else n=$(find "$p" \( -mmin -"$MIN" -o -cmin -"$MIN" \) -print -quit 2>/dev/null); fi
  [ -z "$n" ] && printf "%s\n" "$p"' _ < "$ALL" > "$OLD"

# 2. state-like names (sockets, pids, locks, OS and per-session state)
grep -vE '/(com\.apple\.|launchd[^/]*$|powerlog|claude-501(/|$))|socket|\.sock$|\.pid$|lock' "$OLD" > "$CAND"

# 3. open handles: lsof <dir> does NOT list files beneath it, so take the full list and prefix-filter
PAT=$(printf '%s|' "${RS[@]}" | sed 's/|$//')
lsof -F n +c0 2>/dev/null | awk '/^n\//{print substr($0,2)}' | grep -E "^($PAT)/" | sed 's#^/tmp/#/private/tmp/#' | sort -u > "$OPEN_LIST"
# hash every open file and all of its ancestor paths, so a candidate is open iff it is in the set (O(1) per candidate)
awk 'FILENAME==ARGV[1]{n=split($0,a,"/");s="";for(i=2;i<=n;i++){s=s"/"a[i];o[s]=1};next}!($0 in o)' "$OPEN_LIST" "$CAND" > "$OLD"

# 4. drop children whose parent is also a candidate
awk 'NR==FNR{c[$0]=1;next}{p=$0;sub("/[^/]*$","",p);if(!(p in c))print $0}' "$OLD" "$OLD"
