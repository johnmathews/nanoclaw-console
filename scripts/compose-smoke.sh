#!/usr/bin/env bash
# Starts the app image the way the agent LXC runs it (scripts/compose-smoke.yml: read-only root
# filesystem, no capabilities, uid 10001) and checks it answers: /healthz is exactly {"ok":true},
# the built page is served, and Docker's own healthcheck turns healthy. Leaves nothing running.
set -euo pipefail

cd "$(dirname "$0")"
export APP_IMAGE=${APP_IMAGE:-nanoclaw-console:local}
PROJECT=nanoclaw-console-smoke
BASE=http://127.0.0.1:18000

compose() { docker compose -p "$PROJECT" -f compose-smoke.yml "$@"; }
cleanup() { compose down --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  compose logs --tail 50 >&2 || true
  exit 1
}

compose up -d --wait --wait-timeout 60 || fail "the app did not turn healthy"

body=$(curl -sf "$BASE/healthz") || fail "/healthz did not answer"
[[ $body == '{"ok":true}' ]] || fail "/healthz answered $body"
curl -sf "$BASE/" | grep -q '<title>NanoClaw console</title>' || fail "/ is not the built page"
status=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/nope")
[[ $status == 404 ]] || fail "an unknown /api path answered $status, not 404"

echo "compose-smoke: ok ($APP_IMAGE)"
