#!/usr/bin/env bash
# Fails when web/src/styles/tokens.css is not what `npm run tokens` would write from
# brand/design-system/project/tokens.json: a hand edit, or a tokens.json change without a
# regenerate. Compares against a fresh copy instead of `git diff`, so it works before a commit.
set -euo pipefail

cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

python3 scripts/design_preview.py brand/design-system --tokens-css "$tmp/tokens.css" \
  --dark-selector .dark >/dev/null
grep -v '^@font-face' "$tmp/tokens.css" >"$tmp/expected.css"

if ! diff -u "$tmp/expected.css" web/src/styles/tokens.css; then
  echo "web/src/styles/tokens.css is stale: run \`npm run tokens\` in web/." >&2
  exit 1
fi
