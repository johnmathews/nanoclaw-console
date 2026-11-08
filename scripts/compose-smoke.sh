#!/usr/bin/env bash
# Starts the app image the way the agent LXC runs it (scripts/compose-smoke.yml: read-only root
# filesystem, no capabilities, uid 10001, no Access settings) and checks it answers: /healthz is
# exactly {"ok":true}, Docker's own healthcheck turns healthy, and every other path, the page
# included, is a bare 403, because a console without Access settings fails closed (D12). Leaves
# nothing running.
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
for path in / /api/overview /api/nope; do
  out=$(curl -s -w '\n%{http_code}' "$BASE$path")
  status=${out##*$'\n'}
  body=${out%$'\n'*}
  [[ $status == 403 ]] || fail "$path answered $status without a token, not 403"
  [[ -z $body ]] || fail "$path refused with a body: $body"
done

echo "compose-smoke: ok ($APP_IMAGE)"
