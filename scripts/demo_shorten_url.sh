#!/usr/bin/env bash
# Live product demo: shorten a real URL against the running target_app service and
# show the redirect + analytics actually work. Requires `docker compose up` (or at
# least postgres + target_app) already running.
#
# Usage: ./scripts/demo_shorten_url.sh [long_url]
set -euo pipefail

LONG_URL="${1:-https://www.schwab.com/invest-with-us}"
API_KEY="${API_KEY:-change-me-in-production}"
BASE_URL="${TARGET_APP_URL:-http://localhost:8000}"

section() {
    echo
    printf '%.0s=' {1..66}; echo
    echo " $1"
    printf '%.0s=' {1..66}; echo
}

section "URL Shortener - live demo against $BASE_URL"
echo
echo "Original URL:"
echo "  $LONG_URL"

if ! curl -s -f "$BASE_URL/health" > /dev/null; then
    echo
    echo "ERROR: target_app is not reachable at $BASE_URL - run 'docker compose up' (or 'make up') first." >&2
    exit 1
fi

RESPONSE=$(curl -s -X POST "$BASE_URL/shorten" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{\"long_url\": \"$LONG_URL\"}")

CODE=$(echo "$RESPONSE" | sed -n 's/.*"code":"\([^"]*\)".*/\1/p')
SHORT_URL="$BASE_URL/$CODE"

echo
echo "Shortened URL:"
echo "  $SHORT_URL"

section "Following the redirect"
echo
# GET, not HEAD (-I) - the redirect route doesn't support HEAD.
curl -s -D - -o /dev/null "$SHORT_URL" | grep -i "^location:" | sed 's/^/  /'

section "Analytics (click count after one redirect)"
echo
curl -s "$SHORT_URL/stats" -H "X-API-Key: $API_KEY"
echo
echo
