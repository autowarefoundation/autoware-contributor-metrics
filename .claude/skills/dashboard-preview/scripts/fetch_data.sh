#!/usr/bin/env bash
# Download the deployed dashboard JSON into a directory.
#
# The pipeline needs a GitHub token and roughly an hour to regenerate these
# files, so for front-end work the published copies are the practical source of
# truth: they are real, current, and include the awkward shapes that synthetic
# fixtures tend to miss.
#
# Usage: fetch_data.sh [target-dir]   (default: public)

set -euo pipefail

TARGET="${1:-public}"
BASE="${DASHBOARD_BASE_URL:-https://autowarefoundation.github.io/autoware-contributor-metrics}"

FILES=(
  repositories
  stars_history
  contributors_history
  commits_history
  activity_history
  rankings
  apt_downloads
  arxiv_mentions_history
  arxiv_citations_history
  google_trends_history
)

mkdir -p "$TARGET"
failed=0

for name in "${FILES[@]}"; do
  url="$BASE/$name.json"
  tmp="$(mktemp)"
  if curl -sSf --max-time 120 -o "$tmp" "$url" && python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$tmp"; then
    mv "$tmp" "$TARGET/$name.json"
    printf '  %-30s %10s bytes\n' "$name.json" "$(stat -c%s "$TARGET/$name.json")"
  else
    rm -f "$tmp"
    printf '  %-30s FAILED (kept existing copy if any)\n' "$name.json"
    failed=$((failed + 1))
  fi
done

if [ "$failed" -gt 0 ]; then
  echo "warning: $failed file(s) could not be downloaded" >&2
fi
echo "data in $TARGET/"
