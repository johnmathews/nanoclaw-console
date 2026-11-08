#!/usr/bin/env bash
# Starts the app image the way the agent LXC runs it (scripts/compose-smoke.yml: read-only root
# filesystem, no capabilities, uid 10001, no Access settings) and checks it answers: /healthz is
# exactly {"ok":true}, Docker's own healthcheck turns healthy, and every other path, the page
# included, is a bare 403, because a console without Access settings fails closed (D12); and the
# audit log's named volume, new and empty, is writable by uid 10001 on the read-only root (W15).
# Leaves nothing running, the volume included.
set -euo pipefail

cd "$(dirname "$0")"
export APP_IMAGE=${APP_IMAGE:-nanoclaw-console:local}
PROJECT=nanoclaw-console-smoke
BASE=http://127.0.0.1:18000

compose() { docker compose -p "$PROJECT" -f compose-smoke.yml "$@"; }
cleanup() { compose down --volumes --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  compose logs --tail 50 >&2 || true
  exit 1
}

cleanup  # a volume left by an earlier run would hide what a new one looks like
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

# The audit log: the console's own check, as the action routes run it, inside the container.
writable=$(compose exec -T console python -c \
  'from pathlib import Path; from nanoclaw_console.audit import AuditLog
print(AuditLog(Path("/var/lib/nanoclaw-console/audit")).writable())') ||
  fail "could not run the audit check in the container"
[[ $writable == True ]] || fail "the audit volume is not writable by uid 10001 ($writable)"
mode=$(compose exec -T console stat -c '%u:%g %a' /var/lib/nanoclaw-console/audit)
[[ $mode == "10001:10001 700" ]] || fail "the audit directory is $mode, not 10001:10001 700"
compose exec -T console sh -c 'touch /app/x' 2>/dev/null && fail "the root filesystem is writable"

echo "compose-smoke: ok ($APP_IMAGE)"
