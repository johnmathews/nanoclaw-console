# 2026-11-08 — Scaffold

The repo went from a one-line README to a working skeleton: both images build, `make ci` passes on a
placeholder page, and the workflows that will publish to ghcr are in place. Nothing reads NanoClaw
yet. This is unit W3 of the engineering-team run `manual-20261108T121535Z` in proxmox-setup; its
decisions are copied into [docs/decisions.md](../docs/decisions.md) so they outlive that run.

## What was built

- **`api/`**: uv project `nanoclaw-console-api`, package `nanoclaw_console`. FastAPI with
  `GET /healthz` (`{"ok": true}`, no auth: the container healthcheck), a placeholder
  `GET /api/overview` (`{"status": "scaffold"}`), and the built SPA from `STATIC_DIR` with an
  `index.html` fallback for client routes. An unknown `/api/…` path stays a 404 rather than getting
  HTML with a 200. The OpenAPI docs are off.
- **`broker/`**: uv project `nanoclaw-console-broker`, package `nanoclaw_broker`, standard library
  only. It parses `--socket` and `--ncl-socket` and exits 69 (`EX_UNAVAILABLE`) saying it is not
  implemented, so a deploy before W4 fails loudly instead of looking healthy.
- **`web/`**: tracker's Vue 3 / Vite / Tailwind 4 / reka-ui / Pinia setup, moved under `web/`, with
  tracker's lockfile as the starting point so the versions match. One page, "NanoClaw console", that
  asks `/api/overview` and says whether it answered.
- **`brand/design-system/`**: tracker's system reused (D9). Same token values, usage notes rewritten,
  13 generic cards kept, tracker's product cards and wordmark left out, a new README, foundations and
  voice. The gate (`scripts/check_design_system.py`) and the token generator
  (`scripts/design_preview.py`) are tracker's copies (version 1, the skill's current version).
- **Images**: `Dockerfile` (web build stage, then uv-installed API with `web/dist` at
  `/app/static`, uid 10001, a `/healthz` healthcheck) and `broker/Dockerfile` (uid 1000, no port,
  `python -m nanoclaw_broker`). amd64 only.
- **Make and CI**: `make ci` runs lint, typecheck, unit tests, e2e and the design gate locally. GitHub
  runs one lean job; `docker.yml` publishes both images only after that job passes on a push to
  `main`, building the exact commit it passed.

## Choices worth remembering

- **Test first.** The two routes and the broker's argument parsing were written as failing tests
  first (seen red: `test_healthz_returns_only_ok` failed with `assert 404 == 200`;
  `test_parse_args_reads_both_sockets` with `AttributeError: 'Namespace' object has no attribute
  'socket'`), then implemented.
- **e2e runs against `vite preview`**, the production build, not the dev server as tracker's does.
  The console has no development-only style guide to reach, so the build is the honest target.
- **`compose-smoke` runs the image as the host will**: read-only root filesystem, `/tmp` the only
  tmpfs, no capabilities, no new privileges, uid 10001, 256 MB and half a CPU. It passed, so the image
  writes nothing outside `/tmp`.
- **oxlint linted `node_modules`** until the repo had a `.gitignore`: tracker relies on its
  `.gitignore` for that. `node_modules/**` is now in `web/.oxlintrc.json` too.
- **`npm audit`** reports three moderate advisories, all in the dev-only chain
  `@vue/test-utils` → `js-beautify` → `glob`, the same tree tracker carries. The fix npm offers is a
  downgrade of `@vue/test-utils`; left as is.

## Next

W4 builds the broker's ncl client, verb list, redaction and cache; W6 the backend's Access JWT
check and view APIs; W8 and W9 the screens, each starting with the design system's cards.
