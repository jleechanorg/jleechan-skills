#!/bin/bash
# Delete ONE qualified entry after re-validating scope, age and open handles. Prints one tab-separated
# status line: DELETED | PARTIAL | SKIP-bad | SKIP-excluded | SKIP-gone | SKIP-new | SKIP-open.
#   ROOTS="/a:/b" OPEN_LIST=/path/open.txt [MIN=360] [EXCLUDE="*/keepme/*:*/live-dir"] delete_entry.sh PATH
# Fan out with: xargs -0 -n1 -P8 delete_entry.sh < candidates.nul > delete_log.tsv
set -u
D="${1:?unset}"; : "${ROOTS:?}"; : "${OPEN_LIST:?}"; MIN="${MIN:-360}"; EXCLUDE="${EXCLUDE:-}"

ok=0; IFS=: read -r -a RS <<< "$ROOTS"
for r in "${RS[@]}"; do case "$D" in "$r"/?*) ok=1;; esac; done
case "$D" in *..*) ok=0;; esac
[ "$ok" = 1 ] || { printf 'SKIP-bad\t%s\n' "$D"; exit 0; }

if [ -n "$EXCLUDE" ]; then
  IFS=: read -r -a EX <<< "$EXCLUDE"
  for g in "${EX[@]}"; do case "$D" in $g) printf 'SKIP-excluded\t%s\n' "$D"; exit 0;; esac; done
fi

{ [ -e "$D" ] || [ -L "$D" ]; } || { printf 'SKIP-gone\t%s\n' "$D"; exit 0; }
if [ "${CTIME:-1}" = 0 ]; then   # fixtures only: ctime cannot be back-dated
  [ -z "$(find "$D" -mmin -"$MIN" -print -quit 2>/dev/null)" ] || { printf 'SKIP-new\t%s\n' "$D"; exit 0; }
else
  [ -z "$(find "$D" \( -mmin -"$MIN" -o -cmin -"$MIN" \) -print -quit 2>/dev/null)" ] || { printf 'SKIP-new\t%s\n' "$D"; exit 0; }
fi
if grep -qxF -- "$D" "$OPEN_LIST" || grep -qF -- "$D/" "$OPEN_LIST"; then printf 'SKIP-open\t%s\n' "$D"; exit 0; fi

chflags -R nouchg "$D" 2>/dev/null
rm -rf "${D:?}" 2>/dev/null
if [ -e "$D" ] || [ -L "$D" ]; then printf 'PARTIAL\t%s\n' "$D"; else printf 'DELETED\t%s\n' "$D"; fi
