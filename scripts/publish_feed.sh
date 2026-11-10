#!/usr/bin/env bash
# Publishes data/latest.json to the repo's `feed` branch, which holds only that
# one file. Websites read it from:
#   https://raw.githubusercontent.com/<owner>/<repo>/feed/latest.json
# Keeping it on its own branch means the daily update never adds commits to
# `master`. Used by .github/workflows/daily.yml after each morning's email.
#
#   bash scripts/publish_feed.sh [path/to/latest.json]
set -euo pipefail

SRC="$(realpath "${1:-data/latest.json}")"
if [ ! -f "$SRC" ]; then
  echo "No $SRC — nothing to publish"
  exit 0
fi

WT="$(mktemp -d)"
cleanup() { git worktree remove --force "$WT" >/dev/null 2>&1 || true; }
trap cleanup EXIT

if git fetch --quiet origin feed 2>/dev/null; then
  git worktree add --quiet -B feed "$WT" FETCH_HEAD
else
  # First publish: start an empty branch with no history from master.
  git worktree add --quiet --detach "$WT"
  git -C "$WT" checkout --quiet --orphan feed
  git -C "$WT" rm -rf --quiet . >/dev/null
fi

cp "$SRC" "$WT/latest.json"
git -C "$WT" add latest.json
if git -C "$WT" diff --cached --quiet; then
  echo "latest.json unchanged — nothing to publish"
  exit 0
fi
read_date='import json,sys; print(json.load(open(sys.argv[1]))["date"])'
EDITION_DATE="$(python3 -c "$read_date" "$SRC" 2>/dev/null || python -c "$read_date" "$SRC" 2>/dev/null || date -u +%F)"
git -C "$WT" commit --quiet -m "edition $EDITION_DATE"
git -C "$WT" push --quiet origin feed
echo "Published edition $EDITION_DATE to the feed branch"
