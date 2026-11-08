# 2026-11-08 — Console backend

The console's API went from a scaffold with a placeholder `/api/overview` to the real backend: the
Access JWT check on every route, a client for the broker's socket, Loki signals for Claude health
and NanoClaw's host errors, and the five views plus a task detail that the web app (W8, W9) will
draw. This is unit W6 of the engineering-team run `manual-20261108T121535Z` in proxmox-setup. The
design and the JSON contract are in [docs/architecture.md](../docs/architecture.md) §4; the
settings are in [docs/development.md](../docs/development.md) §7.

## What was built

- **`access.py`**, ported from the SRE agent's Upgrade Advisor (RS256 only, keys by `kid` cached
  1 h, an unknown `kid` refetches at most once a minute, `aud` and `iss` required, 60 s leeway),
  plus two checks of its own: `type` must be `app` (Access's team-domain `org` token is refused)
  and the email must be on `ALLOWED_EMAILS`. It is an ASGI middleware in front of everything,
  static files and unknown paths included; only `GET /healthz` is open (D12). Every refusal is a
  bare 403 with no body. With `ACCESS_TEAM_DOMAIN`, `ACCESS_AUD` or `ALLOWED_EMAILS` unset, it
  refuses everything and logs why once, which is what W10 needs before W12's AUD exists.
- **`broker_client.py`**: one JSON line each way per connection (D14), 30 s per call, 16 MiB
  replies, 4 calls in flight. Errors keep the broker's code and nothing else of its text.
- **`loki.py`**, **`claude.py`**, **`host_logs.py`**: OneCLI's `{container="onecli"}` lines give
  the last agent call, the last success, the agent call count and the 401/403 counts. Agent
  calls are the `?beta=true` URLs; W5's probe calls `/v1/messages` bare and gets 400 when the
  token is good, so its 400s never look like agent failures, while its 401s still count. The
  status rule (failing, then degraded, then ok, else unknown) is in architecture.md §4.4.
- **`schedule.py`**: cron in words and the next fire time with `cronsim`, in `NANOCLAW_TIMEZONE`
  (default `Europe/Amsterdam`); "overdue on resume" for a paused task whose `process_after` has
  passed (F9); series age from the epoch-ms time inside NanoClaw's ids (F20).
- **`views.py`**: `/api/overview`, `/api/groups`, `/api/tasks`, `/api/tasks/{id}`,
  `/api/permissions`, `/api/problems`. Every read runs in parallel; a failed read leaves a null
  or empty field and an entry in `sources`, never a 500. Only the task detail can be a 404 or a
  503.

## Choices worth remembering

- **NanoClaw's cron runs in Amsterdam time.** Every `process_after` in the fixture matches its
  cron in `Europe/Amsterdam` (`0 9 * * 1` → `2026-11-09T08:00Z`, 09:00 CET), so the zone is a
  setting with that default, not UTC.
- **Series age comes from the id.** `tasks list`'s age is the current occurrence's (a task with
  11 846 runs showed minutes). NanoClaw ids are `<prefix>-<epoch ms>-<random>` and a series id is
  its first occurrence's id (`task-1778399790530-…` is 2026-05-10, which matches the paused task's
  history). Hand-named series (`weekly-…`) get `null`, not a guess.
- **Fields are picked, never passed through.** The broker redacts, and the console still names
  every field it returns, so an MCP header value, an env value, a script or an approval payload
  cannot reach the web app even if the broker ever sent one. A test plants all of those
  unredacted in the fake broker and checks that no view contains them.
- **Host log samples are sanitised again** (URLs to `scheme://host`, `Bearer` values and secret-
  looking `key=value` values masked), because those lines are free text NanoClaw wrote.
- **New dependencies:** `pyjwt[crypto]` 2.15.1 (with `cryptography` 50.0.2), `cronsim` 2.8 (its
  diff from 2.7 is two small bug fixes; it ships `explain()` and `py.typed`), `tzdata` 2026.6 (so
  zone data never depends on the image), and `httpx2` 2.16 moved from dev to runtime for the JWKS
  and Loki calls. Context7 was not available in this session; cronsim's API was read from its
  wheel and tried on every live cron before use.
- **The tests' fakes are real enough to be wrong.** The fake broker is a threaded Unix socket
  server; the fake Loki is an httpx2 transport that runs a small LogQL subset (selectors, `|=`,
  `|~`, `sum(count_over_time(…))`), so a planted log line proves the queries select it.

## Test first

Docs first (architecture.md §4, development.md §7), then the tests, then the code.

- **Collection, before any code:** `ImportError: cannot import name 'Services' from
  'nanoclaw_console.app'`, and `ModuleNotFoundError` for `access`, `broker_client`, `claude`,
  `host_logs`, `loki` and `schedule`.
- **Against a skeleton app** (the new settings, no Access check, the old placeholder): the JWT
  matrix failed 80 of 80 with `assert 200 == 403` (8 bad tokens × 10 routes, static files
  included), `test_missing_config_fails_closed` 4 of 4 with `assert 200 == 403`,
  `test_only_exact_healthz_is_open` 4 of 4, `test_the_two_paused_series_are_overdue_on_resume`
  with `assert 404 == 200`, and `test_401s_in_the_last_hour_make_claude_degraded` with
  `KeyError: 'claude'`.
- **Red after the first implementation:** `test_sample_is_sanitised[…token="abc123"…]` (`'abc123'
  is contained here`: the secret-key pattern needed a character before `token`, so a key named
  exactly `token` or `password` slipped through); and `test_a_paused_task_in_full`
  (`{'has_script': True} != {'has_script': False}`), where the test was wrong: the broker's
  fixture had a planted script on that task, and the broker reports `has_script` from it.
- **Mutation checks** on the security-relevant tests: removing the `type == "app"` check fails 15
  tests; letting an unexpected verifier error propagate fails
  `test_an_unexpected_error_in_the_check_is_a_403` with the `RuntimeError`; counting the probe's
  lines as agent traffic fails three Claude tests (`assert 400 == 200`).

Result: 375 tests, 99 % branch coverage on `api/` (floor 95), ruff and mypy strict clean. The
image builds and, run hardened with no Access settings, answers `/healthz` with `{"ok":true}` and
`/` and `/api/overview` with an empty 403.

## Next

- `scripts/compose-smoke.sh` still expects `/` to serve the page and `/api/nope` to be a 404
  without a JWT; with the Access check both now get an empty 403, which is the right answer for a
  container with no Access settings. The script needs to expect that (outside this unit's
  footprint, so left for the lead).
- W8 and W9 build on the shapes in architecture.md §4.7. W15 adds the four POST routes; nothing
  in release 1 takes a verb or a free-form parameter.
