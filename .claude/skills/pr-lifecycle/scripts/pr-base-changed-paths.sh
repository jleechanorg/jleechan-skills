#!/usr/bin/env bash
# Resolve a PR's true base through the GitHub API and print the complete
# base...head changed-path set for the documentation-only /er exception.
# Usage: pr-base-changed-paths.sh [PR_NUMBER]  (run inside the PR's checkout)
set -euo pipefail

PR_NUMBER=${1:-$(gh pr view --json number --jq '.number')}
if ! BASE_DATA=$(gh api "repos/{owner}/{repo}/pulls/${PR_NUMBER}" \
  --jq '[.base.ref, .base.repo.clone_url, .base.repo.ssh_url] | @tsv'); then
  echo "Error: could not resolve PR base through the GitHub API" >&2
  exit 1
fi
IFS=$'\t' read -r BASE_BRANCH BASE_CLONE_URL BASE_SSH_URL <<<"$BASE_DATA"
EXPECTED_BASE_DATA="${BASE_BRANCH}"$'\t'"${BASE_CLONE_URL}"$'\t'"${BASE_SSH_URL}"
if [[ "$BASE_DATA" != "$EXPECTED_BASE_DATA" ||
      -z "$BASE_BRANCH" || -z "$BASE_CLONE_URL" || -z "$BASE_SSH_URL" ||
      "$BASE_CLONE_URL" == "null" || "$BASE_SSH_URL" == "null" ]]; then
  echo "Error: GitHub API returned an incomplete PR base" >&2
  exit 1
fi

normalize_repo_url() {
  python3 - "$1" <<'PY'
import re
import sys
from urllib.parse import urlsplit

raw = sys.argv[1].strip().rstrip("/")
scp = re.fullmatch(r"(?:[^@/]+@)?([^:]+):(.+)", raw)
if scp and "://" not in raw:
    normalized = f"{scp.group(1).lower()}/{scp.group(2)}"
elif "://" in raw:
    parsed = urlsplit(raw)
    if parsed.scheme == "file":
        normalized = parsed.path
    elif not parsed.hostname:
        raise SystemExit(1)
    else:
        normalized = f"{parsed.hostname.lower()}/{parsed.path.lstrip('/')}"
else:
    normalized = raw
print(re.sub(r"\.git$", "", normalized.rstrip("/")))
PY
}

if ! BASE_CLONE_ID=$(normalize_repo_url "$BASE_CLONE_URL") ||
   ! BASE_SSH_ID=$(normalize_repo_url "$BASE_SSH_URL"); then
  echo "Error: could not normalize canonical base repository URLs" >&2
  exit 1
fi

MATCHING_REMOTES=()
while IFS= read -r remote; do
  url=$(git config --get "remote.${remote}.url") || continue
  remote_id=$(normalize_repo_url "$url") || continue
  if [[ "$remote_id" == "$BASE_CLONE_ID" || "$remote_id" == "$BASE_SSH_ID" ]]; then
    MATCHING_REMOTES+=("$remote")
  fi
done < <(git remote)

if [[ ${#MATCHING_REMOTES[@]} -ne 1 ]]; then
  echo "Error: expected exactly one remote for '$BASE_CLONE_URL'; found ${#MATCHING_REMOTES[@]}" >&2
  exit 1
fi
BASE_REMOTE=${MATCHING_REMOTES[0]}

git fetch "$BASE_REMOTE" "+refs/heads/${BASE_BRANCH}:refs/remotes/${BASE_REMOTE}/${BASE_BRANCH}"
git diff --name-only "refs/remotes/${BASE_REMOTE}/${BASE_BRANCH}...HEAD"
