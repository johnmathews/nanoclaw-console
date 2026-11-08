# 2026-11-08 — Broker extra reads and two redaction fixes

The broker gained its last release-1 reads: `health`, `usage`, `task-file`, `mount-allowlist` and
`claude-probe`, so it now has 20 verbs, none of which writes. This is unit W5 of the
engineering-team run `manual-20261108T121535Z` in proxmox-setup. The design is in
[docs/architecture.md](../docs/architecture.md) §3.8; the decisions are B11-B18 in
[docs/decisions.md](../docs/decisions.md). Two redaction bugs found in the review of the W4
commit were fixed first, each test seen red before the fix.

## The two redaction fixes

- **`strip_userinfo` stopped at the first `@`.** `https://u:p@ss@host/x` became
  `https://•••@ss@host/x`, and `//u:p@host/` was not matched at all. Red:
  `AssertionError: assert 'https://•••@ss@host/x' == 'https://•••@host/x'`, and
  `assert '//u:p@host/' == '//•••@host/'`. The pattern now takes the whole authority and replaces
  up to its last `@`, as `urlsplit` reads it.
- **`NclError` returned ncl's free text.** Red: `assert 'invalid-args: bad flag --token
  PLANTED-SECRET-ncl-text' == 'ncl rejected the request (invalid-args)'`. The client now gets the
  code and a fixed sentence (a code that is not a short kebab-case word becomes `unknown`). The
  text goes to the log as `detail`, through `redact_text`.

Writing the tests for the new reads turned up a third bug in the same regex. A 256 KiB task file
of letters took longer than the 25 s request deadline: a scheme could start at every position of a
run of scheme characters, so the pattern was quadratic. A lookbehind makes it linear (B16). That
test hangs without the fix and passes in 0.04 s with it. It also covered W4's `strip_userinfo`
on any long string an agent controls, such as a group name.

## What the live host showed

Checked read-only on the agent host (NanoClaw `479a9510`), then again through the broker:

- The `usage` frame's `data` is the rendered text, a plain string. The parser reads the
  `*Current week (all models)*` section; the live string gave 39, later 40.
- `health` answers 503 with the full JSON when `healthy` is false, so 503 counts as data.
- OneCLI's container-config has `env.HTTPS_PROXY` with both a user and a password, and a
  `caCertificate` that Python 3.13's strict verification accepts. The proxy listens on
  `127.0.0.1:10255` as well as the docker bridge, which is what the probe uses.
- `mount-allowlist.json` has three top-level keys, not one: `allowedRoots`, `blockedPatterns` and
  `nonMainReadOnly`. It is returned whole.
- `python:3.13-slim` carries tzdata, so `Europe/Amsterdam` resolves in the broker image.

## Test first

Every new module's test file was written first and seen red at collection (`ModuleNotFoundError`),
except the cache, which failed with `TypeError: get() got an unexpected keyword argument 'ttl'`.
The probe's tests use a fake OneCLI API and a fake MITM proxy that terminates TLS with a CA made by
the openssl CLI (skipped where it is missing). They plant a proxy token and check it is absent from
the result, the log, stdout, stderr and `repr` in every failure mode: a refusing proxy, a proxy that
does not speak TLS, a certificate from another CA, a hang, a closed port, a bad container-config and
an exception whose message holds the token. Changing the logged error from the exception's type to
its message turns the last of these red.

The shared `start_broker` fixture and `ask` moved from `test_server.py` to `conftest.py`, since
`test_reads.py` needs them too.

Result: 517 tests, 99 % branch coverage on `broker/` (floor 95), ruff and mypy strict clean.

## Live check

The package was copied to a temp directory on the agent host and run as john against the real
`ncl.sock`, `groups/`, `mount-allowlist.json` and `127.0.0.1:10254`. `health`, `usage`,
`mount-allowlist` and `claude-probe` (`ok`, HTTP 400) answered; `task-file` returned the
documentation-summary task's file (`documentation-summary.md`, 2912 bytes) and 13 of the 16 tasks'
files (the other 3 have prompts that name no file). The proxy token's first 8 characters and its
Basic-auth form were grepped for in all 22 captured outputs and the broker log: 0 matches. The
temp directory was removed afterwards.

## Next

W6 builds the console's broker client on these shapes, which are unchanged from the plan. The
deployment (W10) must mount `groups/` and the host's `mount-allowlist.json` read-only into the
broker, give it host networking (the probe and `health` use loopback), and pass `--mount-allowlist`
if it mounts the file somewhere other than `/etc/nanoclaw/mount-allowlist.json`.
