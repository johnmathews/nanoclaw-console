# 2026-11-08 — Broker core

The broker went from a stub that exited 69 to the working security boundary: an ncl client, a
frozen registry of the 15 release-1 read verbs, redaction, a cache and the Unix socket the console
will talk to. This is unit W4 of the engineering-team run `manual-20261108T121535Z` in
proxmox-setup. The design is in [docs/architecture.md](../docs/architecture.md) §3; the choices
made while building are B5-B10 in [docs/decisions.md](../docs/decisions.md).

## What NanoClaw's socket really does

Read on the agent host, NanoClaw `479a9510` (the local fork clone is far behind, so it was not
used):

- One `{"id", "command", "args"}` line per connection; one reply line; the server then ends the
  connection (`src/cli/socket-server.ts:88-138`). `--id X` arrives as `{"id": "X"}` and a bare
  `--all` as `{"all": true}` (`src/cli/parse-argv.ts:24-33`); `--json` never reaches the server.
- Every connection is the trusted host (`socket-server.ts:126`), and the server dispatches every
  line it receives, even though it answers only the first (`socket-server.ts:93-97`). The broker
  writes exactly one `json.dumps` line, which cannot contain a raw newline.
- Unknown commands fall back to the longest registered dash-prefix, with the rest as the id
  (`src/cli/dispatch.ts:64-77`). The broker never sends a name outside its registry.
- `tasks list --all` is the host default already (`src/cli/resources/tasks.ts:448-450`) and only
  covers task sessions with status `active`; no flag reaches closed ones. Sent anyway, for
  explicitness.
- The reply's `human` field is server-rendered text; the broker drops it.
- The client must not half-close after writing: Node's `net.Server` defaults to
  `allowHalfOpen: false`, so a FIN would end the connection before the asynchronous reply.

## Fixtures from the live host, scrubbed there

A capture script ran on the host, called every read verb over `ncl.sock`, and scrubbed the replies
in the same process before printing: free text became lorem ipsum, ids became consistent fixture
ids, MCP `headers`, `env`, `url` and `args` became fakes, and a final check refused to print
anything still shaped like a bearer token or a URL query. Then 17 fake secrets were planted, each
containing `PLANTED-SECRET`: bearer headers, an MCP env value, a URL with userinfo, a secret path,
a query and a fragment, an MCP `args` token, a shell `command`, an unknown MCP field, a top-level
`env` and a new field in a group config, a task `script` on both `get` and `list`, an approval
`payload`, `human` text, a URL with userinfo inside a name, and a `*_url` key.

## Test first

All six test files were written before the code and seen red at collection, for example
`tests/test_verbs.py:7` (`ModuleNotFoundError: No module named 'nanoclaw_broker.errors'`) and
`tests/test_main.py:12` (`cannot import name 'DEFAULT_NCL_SOCKET'`). Then two tests stayed red
after the first implementation:

- `test_bad_socket_modes_are_refused[0o660]`: `int("0o660", 8)` accepts the prefix. The mode
  parser now takes plain octal digits only.
- `test_an_empty_connection_gets_bad_request`: the test sent nothing and never closed, so the read
  timeout answered. The test now half-closes, which is what it meant.

A sync test that calls `asyncio.run()` after an async test leaked pytest-asyncio's loop
(ResourceWarnings at session end). `main()` is now tested with `asyncio.run` stubbed, and `_run`
as an async test that receives a real SIGTERM.

Result: 283 tests, 99 % branch coverage on `broker/` (floor 95), ruff and mypy strict clean.

## Live check

The broker source was copied to `/tmp/w4-broker` on the agent host and run there as john with the
host's Python 3.13.5 against the real `ncl.sock`. Each verb was called once through it and compared
with `./bin/ncl <verb> --json`, printing counts and key sets only. Every count matched (15 groups,
17 messaging groups, 14 wirings, 16 destinations, 80 sessions, 16 tasks, 2 roles, 2 members, 0
policies, 1 approval, 6 users, 3 dropped-message rows; `groups-get` and `groups-config-get` for all
15 groups, `tasks-get` for all 16 tasks), and every key set matched once `script` and `payload` were
taken away. Raw ncl returned `Bearer` in 2 of the 15 group configs; the broker returned it in none,
and its log never contained it. `tasks-update` got `unknown_verb`. SIGTERM exited 0 and removed the
socket. `/tmp/w4-broker` was removed afterwards.

## Next

W5 adds the broker's other reads (health, usage, task files, the mount allowlist, the Claude
probe) as more registry entries or sibling handlers; W6 builds the console's broker client on the
protocol in architecture.md §3.3. W15 adds the four write verbs with `cacheable=False`; the
uncacheable path through the cache's in-flight cap already exists and is tested.
