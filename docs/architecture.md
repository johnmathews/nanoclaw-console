# Architecture

> Purpose
>
> What the NanoClaw console is made of: the two images this repo builds, which of them holds
> NanoClaw's authority, how the broker guards it (verb list, redaction, cache), and how the
> console's backend checks the Access JWT, derives Claude health and answers the web app (§4,
> whose JSON shapes are the web app's contract), and how the web app draws it (§5).

## 1. Overview

The console shows NanoClaw v2's state on the agent LXC: Claude health, groups and channels with
their permissions, scheduled tasks, and errors and warnings. Release 1 is read-only. Release 2
adds four reversible actions (pause, resume and run a task; restart a group) behind a
confirmation and an audit log ([decisions.md](decisions.md), D4).

It never imports or edits the NanoClaw fork. Its only coupling to NanoClaw is the frame format of
NanoClaw's control socket, `data/ncl.sock` (D1).

## 2. Two images

| Image                                       | Built from          | Runs as      | Holds                                                    |
| ------------------------------------------- | ------------------- | ------------ | -------------------------------------------------------- |
| `ghcr.io/johnmathews/nanoclaw-console-broker` | `broker/Dockerfile` | uid 1000     | NanoClaw's `ncl.sock` and read-only `data/`, `groups/` |
| `ghcr.io/johnmathews/nanoclaw-console`      | `Dockerfile`        | uid 10001    | Only the broker's socket directory                       |

- **The broker** (`broker/`, package `nanoclaw_broker`) is the only process that can talk to
  NanoClaw. `ncl.sock` grants full control of NanoClaw to anything that can open it, so the broker
  builds every frame itself from a fixed verb list, redacts secrets from what comes back, and
  caches reads. It serves a Unix socket and publishes no port. It is pinned to a SHA on the host and
  upgraded deliberately, never auto-deployed.
- **The console** (`api/` and `web/`, package `nanoclaw_console`) is one FastAPI process that
  serves the JSON API under `/api/` and the built Vue app from `web/dist`. It holds no NanoClaw
  access of its own, only the broker's socket. It runs on a read-only root filesystem and writes
  nothing outside `/tmp`.

**The broker's verb list is the security boundary.** The console's own checks (the Access JWT, its
email allowlist) are defence in depth: a compromised console can ask the broker only for what the
list allows. A NanoClaw write verb is never added anywhere except the broker's list, and only the
four D4 names.

## 3. The broker

The broker (`broker/src/nanoclaw_broker/`) is the only process that opens `ncl.sock`. Release 1
gives it read verbs only: 16 that map to an ncl command (§3.4) and 4 that read something else on
the host (§3.8).

### 3.1 Modules

| Module          | Job                                                                                  |
| --------------- | ------------------------------------------------------------------------------------ |
| `ncl_client.py` | Speaks NanoClaw's frame protocol: one connection per call, one line each way         |
| `verbs.py`      | The frozen verb registry: verb name → ncl command (or local read), id parameters, fixed args, cache TTL |
| `redact.py`     | Removes secrets from every reply before it is cached, logged or returned             |
| `cache.py`      | Per-verb TTL (20 s unless stated), single-flight, at most 2 ncl calls in flight       |
| `reads.py`      | The four reads that are not an ncl command (§3.8): runs them for the server           |
| `health.py`     | `health`: NanoClaw's loopback `/health`                                               |
| `usage.py`      | `usage`: parses ncl's pre-rendered quota text                                         |
| `safefs.py`     | Opens files below a directory with `O_NOFOLLOW` on every component, size-capped       |
| `probe.py`      | `claude-probe`: one empty-body call to Anthropic through OneCLI                       |
| `server.py`     | The Unix socket the console talks to: one JSON line in, one JSON line out            |
| `events.py`     | JSON-line event log on stdout                                                        |
| `__main__.py`   | Command line and SIGTERM handling                                                    |

### 3.2 NanoClaw's frame protocol

Read from NanoClaw `479a9510` on the agent host (`src/cli/frame.ts`, `socket-server.ts`,
`socket-client.ts`, `dispatch.ts`):

- **Request:** one line, `{"id": "<uuid>", "command": "<registered name>", "args": {...}}`.
  `command` is the dash-joined name (`groups-config-get`); `args` is the flag object, with
  `--id X` as `{"id": "X"}` and a bare `--all` as `{"all": true}`. `--json` is client-side only.
- **Reply:** one line, `{"id", "ok": true, "data", "human"?}` or
  `{"id", "ok": false, "error": {"code", "message"}}`. The server then closes the connection.
  `data` is the machine contract and only gains fields; the broker never forwards `human`
  (server-rendered text).
- **Every caller is trusted.** The server treats a connection as the host user and allows every
  command (F1). It also dispatches every line it receives on one connection, even though it
  replies only to the first, so the broker writes exactly one frame per connection and builds
  it with `json.dumps` (which escapes newlines).
- **The socket is recreated** (a new inode) on every NanoClaw restart, so the client opens a fresh
  connection per call and never holds a file descriptor.
- Unknown commands are matched to the longest registered dash-prefix, with the rest taken as
  the id (`groups-get-abc` → `groups-get`, id `abc`). The broker never sends a command name that
  is not in its registry, so this fallback is unreachable through it.

### 3.3 The console-facing protocol

One JSON line in, one JSON line out, then the broker closes the connection:

```json
{"verb": "groups-config-get", "params": {"id": "main-group"}}
{"ok": true, "data": {...}}
{"ok": false, "error": {"code": "invalid_params", "message": "..."}}
```

- The request has exactly the keys `verb` and `params` (`params` may be left out when the verb
  takes none). A `command`, `args` or any other key is refused. The cap is 64 KiB.
- The console never names an ncl command or supplies raw args. The broker looks the verb up in
  its registry, checks that `params` has exactly the registry's parameter names, and builds the
  frame itself.
- Every parameter is an id: a string matching `^[A-Za-z0-9][A-Za-z0-9-]{0,79}$` (the run plan's
  `^[A-Za-z0-9-]{1,80}$`, tightened so an id cannot start with `-`; every live group and task id
  matches).
- Error codes: `bad_request`, `request_too_large`, `unknown_verb`, `invalid_params`,
  `unavailable` (ncl socket missing or refusing), `timeout`, `ncl_error` (ncl answered
  `ok: false`; the client gets the fixed message `ncl rejected the request (<ncl code>)` and
  nothing else of ncl's text, see §3.5), `protocol_error` (ncl's reply was malformed or too
  large) and `internal`.

### 3.4 Release-1 verbs

| Broker verb             | ncl frame                                    |
| ----------------------- | -------------------------------------------- |
| `groups-list`           | `groups-list {}`                             |
| `groups-get`            | `groups-get {id}`                            |
| `groups-config-get`     | `groups-config-get {id}`                     |
| `messaging-groups-list` | `messaging-groups-list {}`                   |
| `wirings-list`          | `wirings-list {}`                            |
| `destinations-list`     | `destinations-list {}`                       |
| `sessions-list`         | `sessions-list {}`                           |
| `tasks-list`            | `tasks-list {"all": true}`                   |
| `tasks-get`             | `tasks-get {id}`                             |
| `roles-list`            | `roles-list {}`                              |
| `members-list`          | `members-list {}`                            |
| `policies-list`         | `policies-list {}`                           |
| `approvals-list`        | `approvals-list {}`                          |
| `users-list`            | `users-list {}`                              |
| `dropped-messages-list` | `dropped-messages-list {}`                   |
| `usage`                 | `usage {}`, parsed (§3.8), cached 5 min      |

There are no write verbs. Release 2 adds `tasks-pause`, `tasks-resume`, `tasks-run` and
`groups-restart`, each with `id` only and marked uncacheable (D4); nothing else is ever added.

Two limits of ncl that the console inherits:

- `tasks-list` covers task sessions whose status is `active` only. `--all` is accepted for
  explicitness but is already the host default (`tasks.ts:448-450`); no flag reaches tasks in
  closed sessions.
- The generic `*-list` verbs return at most 200 rows, newest first (`crud.ts:197`).

### 3.5 Redaction

Applied to `data` inside the cache loader, so nothing unredacted is cached, logged or returned.
The rules apply to every verb's reply, wherever the key appears:

- **`headers` and `env` objects:** every value becomes `"•••"`; the keys stay, so the UI can
  show which header or variable exists.
- **MCP server entries** (each value of `mcp_servers`): `type` and `transport` pass through;
  `url` is reduced (below); `command` passes only if it is a plain path, otherwise it is masked;
  each `args` item is masked (stdio servers take tokens as arguments); any other key's value is
  masked. Unknown fields are therefore hidden until someone decides they are safe.
- **URLs** (any `url` or `*_url` key, and every URL inside an MCP entry) become
  `scheme://host[:port]`. Userinfo and the query string are the obvious leaks, but paths carry
  secrets too (Home Assistant's MCP webhook is `/api/webhook/mcp_<secret>/…`), so the path and
  fragment go as well. A value that does not parse as a URL with a host becomes `"•••"`.
- **Userinfo anywhere:** any string containing `scheme://user[:pass]@` has the userinfo replaced
  by `•••`.
- **`script`** is removed and `has_script: true|false` is set in its place; an existing
  `has_script` (`tasks-list`'s 0 or 1) becomes a boolean.
- **`payload`** (approvals) is removed.
- **Userinfo ends at the last `@`.** `strip_userinfo` matches the whole authority (up to the
  first `/`, `?` or `#`) and replaces everything before its last `@`, as `urlsplit` reads it, so
  a password containing `@` leaves no fragment behind. A scheme-less `//user:pw@host` is covered.
- **ncl's error text never reaches a client.** An `ok: false` reply is reported as
  `{"code": "ncl_error", "message": "ncl rejected the request (<ncl code>)"}`; the code is ncl's
  own if it is a short kebab-case word, otherwise `unknown`. ncl's free text can repeat a secret
  from the request, so it goes only to the broker's log (`detail` on the `request` event), after
  `redact_text`: each URL cut to `scheme://host[:port]`, `Bearer` and `Basic` values masked, 500
  characters at most. A bare secret with no such shape cannot be recognised, which is why the text
  is not sent to the client at all.
- **`groups-config-get`** keeps only the top-level keys NanoClaw's `presentConfig` returns today
  (`groups.ts:74-94`), so an `env` key, or any field added upstream later, is dropped until
  added to the list.

### 3.6 Cache and load

Every ncl call runs on NanoClaw's one event loop, on a 2-core LXC that is already busy (F12), so:

- Each (verb, params) answer is cached for 20 s.
- Concurrent identical requests share one ncl call (single-flight).
- At most 2 ncl calls are in flight at once; the rest queue.
- Errors are not cached: the next request tries again. Single-flight and the cap of 2 already
  bound the load a failing verb can cause.
- Each ncl call times out after 10 s; a whole request (queueing included) after 25 s. Replies over
  8 MiB are refused.

### 3.7 The broker's socket and log

- `--socket` (default `/run/nanoclaw-console/broker.sock`). A stale socket at the path is removed
  at start; any other file there is refused. The socket is created with umask `0177` (so it is
  never more open than `0600` while being set up), then set to `--socket-mode` (default `0660`)
  and, with `--socket-group <gid>`, given that group. The broker runs as `1000:1000` with the
  console's gid added, so it can hand the socket to that group without root.
- `--ncl-socket` (default `/srv/apps/nanoclaw/data/ncl.sock`). The broker starts even when
  NanoClaw is down and answers `unavailable` until it is back.
- For the extra reads (§3.8): `--groups-dir` (default `/srv/apps/nanoclaw/groups`),
  `--mount-allowlist` (default `/etc/nanoclaw/mount-allowlist.json`; the deployment mounts
  `~/.config/nanoclaw/mount-allowlist.json` read-only there), `--health-port` (default 3002),
  `--onecli-url` (default `http://127.0.0.1:10254`) and `--probe-agent-group` (default
  `ag-1779373702795-5wbiev`, `main-group`).
- SIGTERM or SIGINT closes the server, removes the socket and exits 0.
- The log is JSON lines on stdout: one `request` event per request with the verb (only a known
  verb name), the validated ids, the cache result (`hit`, `miss`, `shared`), the outcome and the
  duration. It never contains reply data. An ncl rejection adds `ncl_code` and the redacted
  `detail` (§3.5).

### 3.8 The extra reads

Four verbs read something other than an ncl command, and `usage` post-processes ncl's text. None
takes anything but an id; none has a write counterpart. Local reads do not use one of the 2 ncl
slots (task-file's own ncl calls do).

| Verb               | Params | Cache | Answer                                                           |
| ------------------ | ------ | ----- | ---------------------------------------------------------------- |
| `health`           | none   | 60 s  | NanoClaw's `/health` JSON as is, or `{"available": false}`       |
| `usage`            | none   | 5 min | `{weekly_pct, resets_at, resets_text, source}`                   |
| `task-file`        | `id`   | 20 s  | `{name, content, truncated}` or `{"file": null}`                 |
| `mount-allowlist`  | none   | 60 s  | the allowlist file as is, or `{"available": false}`              |
| `claude-probe`     | none   | 5 min | `{status, http_status, checked_at}`                              |

- **`health`.** `GET http://127.0.0.1:<health-port>/health`. HTTP 200 and 503 (NanoClaw answers
  503 when `healthy` is false) both carry the JSON; any other status, a body that is not a JSON
  object or over 64 KiB, a closed port or a timeout gives `{"available": false}`, not an error.
  `healthy` covers channels and the message loop only, never Claude (F8).
- **`usage`.** The `usage` ncl command returns text, not fields (`getUsageText`). The broker takes
  the `*Current week (all models)*` section: `weekly_pct` is the integer before `% used`;
  `resets_text` is the line after `Resets `, for example `Nov 10, 9pm (Europe/Amsterdam)`;
  `resets_at` is that moment as ISO 8601 with the zone's offset, the year taken as the next
  occurrence (a line with only a time means today), or `null` if the zone is unknown to the
  image or the line does not parse. `source` is always `host ~/.claude login`: this is the
  host login's quota, not the token NanoClaw's agents use (D6). Text with no such section (a
  failure message, "No usage data available.") gives `null` for the other three fields.
- **`task-file`.** `id` is the task's series id. A task's run log is `groups/<folder>/tasks/<series>.md`
  and `tasks-get` returns it as `recent_log`; "what the task will do" is the file its prompt names.
  The broker calls `tasks-get` for the prompt and `agent_group_id`, takes the name from a prompt
  that starts `Read /workspace/agent/tasks/<name>.md` (name `[A-Za-z0-9._-]{1,80}\.md`; no match
  gives `{"file": null}`), calls `groups-get` for the folder, and reads
  `<groups-dir>/<folder>/tasks/<name>`. The group folder is writable inside the agent
  containers, so a symlink planted there is the threat. The read opens `<groups-dir>` as a
  directory, then each of `<folder>`, `tasks` and `<name>` with `openat`-style `dir_fd`,
  `O_NOFOLLOW` (and `O_DIRECTORY` for directories), checks with `fstat` that the leaf is a
  regular file and reads at most 256 KiB (`truncated` says if more was there). A missing file or a
  refusal (symlink, not a regular file, odd folder name) gives `{"file": null}`, and a refusal is
  logged as `task_file_refused` with the reason. Instruction files can hold a pasted key, so
  `content` goes through userinfo and `Bearer` masking before it is returned.
- **`mount-allowlist`.** The JSON file NanoClaw reads (`allowedRoots`, `blockedPatterns`,
  `nonMainReadOnly`), opened through the same safe reader, capped at 256 KiB, returned as parsed
  with the common redaction. It is not an ncl command, so the deployment mounts the host's
  `~/.config/nanoclaw/mount-allowlist.json` read-only.
- **`claude-probe`** (F18, proven by W2). NanoClaw's agents reach Claude through OneCLI. With a
  body of `{}`, Anthropic checks the credential before the body, so `POST /v1/messages` through
  OneCLI answers 400 when the injected token is accepted and 401 when it is not, and spends no
  tokens. The broker has no Docker socket, so it takes an agent's proxy credentials from
  `GET <onecli-url>/v1/container-config?identifier=<agent group>` (the response's
  `env.HTTPS_PROXY` and `caCertificate`), connects to **`127.0.0.1`** on the proxy's port (the
  host in the response, `host.docker.internal`, is never contacted), sends `CONNECT
  api.anthropic.com:443` with `Proxy-Authorization: Basic`, verifies TLS against the returned CA,
  and sends `Authorization: Bearer placeholder`, `anthropic-version: 2023-06-01` and `{}`. The
  mapping: **400 is `ok`; 401 or 403 is `failing`; everything else (another status, a timeout, a
  TLS or proxy failure, a container-config failure) is `unknown`**, with `http_status` null when
  there was no answer. The broker cannot see OneCLI's `injections_applied`, so a 400 does not
  prove injection. The proxy token never appears in a response, a log line or an exception text:
  every failure on this path is reduced to `unknown` before anything is formatted. The probe
  shows in OneCLI's log as `url=…/v1/messages` without `?beta=true`, which is how the console
  tells it from agent traffic.

## 4. The console backend

The console's API (`api/src/nanoclaw_console/`) answers the web app. It reads NanoClaw only through
the broker (§3.3) and Loki, and composes what it reads into five views and a task detail.

### 4.1 Modules

| Module             | Job                                                                                     |
| ------------------ | --------------------------------------------------------------------------------------- |
| `config.py`        | Settings from the environment ([development.md](development.md) §7)                     |
| `access.py`        | Verifies the Cloudflare Access JWT and the email allowlist; the middleware that applies it |
| `broker_client.py` | The broker's protocol: one JSON line each way per connection, typed errors              |
| `loki.py`          | Loki's query API: log lines and counts, size- and time-bounded                          |
| `claude.py`        | Claude health: OneCLI's signals from Loki, the broker's probe, the status rule (§4.4)  |
| `host_logs.py`     | NanoClaw's host errors and warnings from Loki, grouped by message (§4.5)               |
| `schedule.py`      | Cron in plain words, the next fire time, "overdue on resume", series age (§4.6)        |
| `views.py`         | The view payloads (§4.7): broker and Loki reads in parallel, degraded answers           |
| `ttl_cache.py`     | A 30 s cache for the Loki-derived signals                                               |
| `app.py`           | Routes, the static web app, wiring                                                      |

### 4.2 The Access check

Every request except `GET /healthz` must carry a valid Cloudflare Access JWT in
`Cf-Access-Jwt-Assertion`, including requests for the web app's static files and for unknown
paths. Ported from the SRE agent (`homelab-sre/sre-agent/src/upgrades/access.py`), plus the `type`
claim and the email allowlist (D3, F6):

- **Keys.** `https://<ACCESS_TEAM_DOMAIN>/cdn-cgi/access/certs`, fetched without following
  redirects, capped at 256 KiB, cached 1 h. Only RSA keys for RS256 with a `kid` are kept. An
  unknown `kid` (Cloudflare rotated its keys) refetches, at most once a minute, so forged `kid`s
  cannot make every request call out.
- **The token.** At most 16 KiB; header `alg` must be `RS256` (so `none` and `HS256` are refused
  before any key is used) and carry a `kid`; signature checked with that key; `aud` must contain
  `ACCESS_AUD`; `iss` must be `https://<ACCESS_TEAM_DOMAIN>`; `exp`, `iat`, `iss` and `aud` are
  required; 60 s leeway for clock skew.
- **`type` must be `app`.** Access also issues `org` tokens (the team-domain session), which carry
  no application audience meant for this console.
- **The email** claim must be on `ALLOWED_EMAILS`, compared case-insensitively. A service-token
  JWT has no `email` and is refused.
- **Fail closed.** If `ACCESS_TEAM_DOMAIN` (or a value that is not a bare `*.cloudflareaccess.com`
  host), `ACCESS_AUD` or `ALLOWED_EMAILS` is empty, every request is refused and the reason is
  logged once at error level. `/healthz` still answers, so the container stays healthy and the
  misconfiguration shows as 403s, not as a restart loop.
- **The refusal** is `403` with an empty body and `Cache-Control: no-store`, whatever the reason.
  The reason goes to the log only, never the token or its claims. An unexpected error inside the
  check is also a 403.
- The verified email is put on the request (`request.state.access_email`) for release 2's audit
  log.

The Access app in front (W12) is the first layer and the firewall rule admitting only cloudflared
and Gatus is the second (D3, D12); this check is the third, and it is what makes a JWT for any
other Access app useless here.

### 4.3 The broker client

- One connection per call to `BROKER_SOCKET`: one `{"verb", "params"}` line out, one line back
  (§3.3). A fresh connection each time, so a recreated broker socket is picked up.
- 30 s per call (the broker gives up at 25 s itself), replies capped at 16 MiB, at most 4 calls
  in flight from the console.
- Errors are typed and carry only a code: `unavailable` (no socket, refused, closed without an
  answer), `timeout`, `protocol_error` (not one JSON object, or too large), or the broker's own
  code (`unknown_verb`, `invalid_params`, `ncl_error`, …). The broker's message text is never
  passed on to a client.
- The console never takes a verb from a request. It takes an id only for the task detail, checked
  against the broker's id pattern first (anything else is a 404).

### 4.4 Claude health

Claude health comes from OneCLI's traffic, never from `usage` (D6, F7, F8). Signals, from Loki
lines of `{container="onecli"}` containing `api.anthropic.com` and `/v1/messages`:

- An **agent call** is a line whose URL is `/v1/messages?beta=true` (the agents' Claude Code SDK
  calls). The broker's probe calls `/v1/messages` with no query string and answers 400 when the
  token is good, so a probe line is never an agent call and its 400s never count against health.
- **Last agent call** (24 h): its time, `status=`, `agent="…"` and `injections_applied=`.
- **Last success**: the time of the last agent call with a 2xx status (24 h).
- **Auth failures**: lines with status 401 or 403, agent or probe, counted over 1 h and 24 h. A
  401 is a real failure either way.
- **Agent calls** over 24 h, for scale.
- **The probe**: the broker's `claude-probe` (§3.8), shown separately.

The status, first match wins:

1. **failing**: the last agent call in 24 h got 401 or 403, or the probe says `failing`.
2. **degraded**: any auth failure in the last hour; or the last agent call got another non-2xx
   status (429, 5xx, …); or it had `injections_applied=0` (OneCLI did not inject the token).
3. **ok**: the last agent call got a 2xx, or the probe says `ok`.
4. **unknown**: none of the above: no agent call in 24 h and no `ok` probe, or neither Loki nor
   the probe answered.

`reasons` lists the sentences that led to the status. Loki's answers are cached 30 s in the
console, so open tabs cost Loki at most one set of queries per 30 s.

The quota is shown beside it as **the host `~/.claude` login's** weekly quota (`usage`, §3.8),
never as NanoClaw's: `ncl usage` reads the host's credentials, not the OneCLI token the agents use
(F7). It plays no part in the status.

### 4.5 Host errors and warnings

From `{job="nanoclaw", level=~"WARN|ERROR|FATAL"}` over 24 h (NanoClaw's host log files, shipped
by the agent host's Alloy), newest 2000 lines (`truncated` says if there were more):

- Only an entry's first line is used (a stack trace arrives joined to its entry); ANSI escapes are
  removed.
- **The message** is the text after `[hh:mm:ss.mmm] LEVEL`, with every `key=value` and
  `key="value"` pair removed, so `Inserted next recurrence originalId="a" seriesId="b"` and the
  same line with other ids group together. `FATAL` counts as an error.
- Each group has its level, message, count, first and last time, and one **sample** line: the
  newest, with URLs cut to `scheme://host[:port]`, `Bearer`/`Basic` values masked and values of keys
  that look secret (`token`, `secret`, `password`, `key`, `auth`, `cookie`) masked, cut to 500
  characters.

### 4.6 Derived task fields

- **Schedule in words and the next fire time.** NanoClaw evaluates a task's cron in the host's
  zone, `NANOCLAW_TIMEZONE` (default `Europe/Amsterdam`; every live `process_after` matches it).
  `cronsim` gives the words ("At 09:03 every day") and the next occurrence after now. The aliases
  `@hourly`, `@daily`/`@midnight`, `@weekly`, `@monthly` and `@yearly`/`@annually` are expanded
  first; anything cronsim cannot read gives `valid: false` and nulls. A task with no recurrence
  is "Once".
- **Next run.** `next_run_at` is NanoClaw's `process_after`, which is when it will run, except for a
  task that will not run: `null` when it is paused (or `completed`, `cancelled`, `failed`, `done`).
- **Overdue on resume** (F9): `status` is `paused` and `process_after` is in the past. NanoClaw
  runs such a task once immediately when it is resumed, then on its schedule.
- **Series age** (F20). `tasks list`'s age is the current occurrence's, not the series'. NanoClaw
  ids are `<prefix>-<epoch ms>-<random>`, and a series id is its first occurrence's id, so
  `series_started_at` is the time in the series id. A series id without one (a hand-named
  series) gives `null`, never a guess.
- **Task file.** The name a prompt points at (`Read /workspace/agent/tasks/<name>.md …`), the same
  rule the broker's `task-file` uses; the detail view adds the file itself.

### 4.7 Routes and answers

| Route                  | What                                                                              |
| ---------------------- | --------------------------------------------------------------------------------- |
| `GET /healthz`         | No auth; exactly `{"ok": true}`, nothing about NanoClaw (D12)                     |
| `GET /api/overview`    | Claude health, NanoClaw's `/health`, the quota, counts and the warnings strip     |
| `GET /api/groups`      | Each agent group with its config, MCP servers, mounts, channels and destinations  |
| `GET /api/tasks`       | Every scheduled task with its schedule in words and derived fields                |
| `GET /api/tasks/{id}`  | One task (series id): full prompt, recent run log and the task file               |
| `GET /api/permissions` | Roles, members, policies, destinations, the mount allowlist, approvals, and what the console cannot see |
| `GET /api/problems`    | Every problem worth a look, and the host log groups                               |
| anything else          | The built web app (`STATIC_DIR`), `index.html` for client routes; an unknown `/api/…` is a 404 |

Release 2 adds `POST` routes for its four actions (D4); release 1 has none, and no route takes a
verb or a free-form parameter.

**Degraded answers.** A view makes all its reads in parallel and answers 200 with whatever
arrived. A field whose read failed is `null` (a count, a block) or empty, and `sources` says which
reads failed with which code:

```json
"sources": {
  "broker": {"ok": false, "errors": {"health": "unknown_verb", "tasks-list": "unavailable"}},
  "loki": {"ok": true, "errors": {}}
}
```

Codes are the broker client's (§4.3) and Loki's (`not_configured`, `unavailable`, `timeout`,
`bad_response`). Only the task detail cannot be partial: an unknown task is `404 {"error":
"not_found"}`, and a broker that cannot answer is `503 {"error": "broker_unavailable", "code"}`.
Every time the console emits is UTC ISO 8601 with milliseconds and `Z`
(`2026-11-08T13:37:45.983Z`), whatever form NanoClaw used. Every answer has `generated_at`.

The shapes below are the contract the web app builds on. `…` stands for the same value type as
shown elsewhere in this section.

**`/api/overview`**

```json
{
  "generated_at": "2026-11-08T14:30:00.000Z",
  "claude": {
    "status": "ok",
    "reasons": ["The last agent call to Claude succeeded (HTTP 200)."],
    "last_agent_call": {"at": "…", "status": 200, "agent": "main-group", "injections_applied": 1},
    "last_success_at": "…",
    "agent_calls_24h": 412,
    "auth_failures_1h": 0,
    "auth_failures_24h": 0,
    "probe": {"status": "ok", "http_status": 400, "checked_at": "…"}
  },
  "nanoclaw": {
    "available": true, "healthy": true, "uptime_seconds": 72739, "message_loop_running": true,
    "channels": [{"name": "slack", "connected": true}],
    "queue": {"active": 1, "max": 0, "waiting": 0},
    "registered_group_count": 15, "active_session_count": 18, "last_message_at": "…",
    "tasks": {"active_count": 14, "paused_count": 2, "next_run_at": "…", "recent_failures": 0}
  },
  "quota": {
    "available": true,
    "label": "Weekly quota of the host's ~/.claude login (not NanoClaw's token)",
    "source": "host ~/.claude login", "weekly_pct": 39, "resets_at": "…",
    "resets_text": "Nov 10, 9pm (Europe/Amsterdam)"
  },
  "counts": {
    "groups": 15, "channels": 17, "wirings": 14, "sessions": 80, "tasks": 16, "tasks_paused": 2,
    "tasks_overdue_on_resume": 2, "pending_approvals": 1, "dropped_messages": 3,
    "host_errors_24h": 8, "host_warnings_24h": 13
  },
  "warnings": ["<problem item, as in /api/problems>"],
  "sources": {"broker": {"ok": true, "errors": {}}, "loki": {"ok": true, "errors": {}}}
}
```

`claude.probe`, `claude.last_agent_call` and `claude.last_success_at` are `null` when absent; the
three counts are `null` when Loki did not answer. `nanoclaw` is `{"available": false, "reason":
"not_answering" | "broker_error"}` when NanoClaw's `/health` did not answer or the broker read
failed. `quota` is `{"available": false, "reason": "broker_error", "label": "…"}` when its read
failed; `weekly_pct`, `resets_at` and `resets_text` are `null` when the text did not parse. Each
count is `null` when its read failed.

**`/api/tasks`** and a task

```json
{
  "generated_at": "…",
  "timezone": "Europe/Amsterdam",
  "tasks": [
    {
      "id": "task-1778399790530-f2euaw",
      "row_id": "task-…",
      "group": {"id": "ag-…", "name": "main-group", "folder": "main"},
      "status": "paused",
      "overdue_on_resume": true,
      "prompt": "Read /workspace/agent/tasks/documentation-summary.md and follow …",
      "task_file": "documentation-summary.md",
      "has_script": false,
      "schedule": {"cron": "3 9 * * *", "words": "At 09:03 every day",
                   "timezone": "Europe/Amsterdam", "valid": true, "next_fire_at": "…"},
      "next_run_at": null,
      "process_after": "2026-05-27T07:03:00.000Z",
      "last_run_at": "2026-05-26T07:03:00.000Z",
      "runs": 5, "failed_runs": 0, "tries": 0,
      "series_started_at": "2026-05-10T07:56:30.530Z",
      "series_age_days": 182,
      "occurrence_created_at": "…",
      "session_id": "sess-…"
    }
  ],
  "sources": {"broker": {"ok": true, "errors": {}}}
}
```

Tasks are sorted by `next_run_at`, paused ones (null) last. `group.name` and `group.folder` are
`null` when the group is not in `groups-list`. `schedule.cron` is `null` for a one-off task.

**`/api/tasks/{id}`** is `{"generated_at", "timezone", "task", "task_file", "sources"}`: `task`
is a task as above plus `recent_log` (the last run-log lines, from `tasks-get`) and
`completed_runs`, with the full prompt from `tasks-get`; `task_file` is `{"name", "content",
"truncated"}` or `null` when the prompt names no file, the file is missing or the read failed.

**`/api/groups`**

```json
{
  "generated_at": "…",
  "groups": [
    {
      "id": "ag-…", "name": "main-group", "folder": "main", "created_at": "…",
      "config": {
        "model": "claude-opus-4-7", "provider": null, "effort": null, "speed": null,
        "assistant_name": null, "cli_scope": "group", "timezone": null, "image_tag": null,
        "max_messages_per_prompt": null, "skills": "…", "packages_apt": [], "packages_npm": [],
        "updated_at": "…",
        "mcp_servers": [
          {"name": "journal", "type": "http", "transport": null,
           "url": "https://mcp.example.internal:8443", "command": null,
           "header_names": ["Authorization"], "env_names": [], "arg_count": 0}
        ],
        "mounts": [{"host_path": "/srv/…", "container_path": "/workspace/…", "read_only": false}]
      },
      "channels": [
        {"wiring_id": "…", "messaging_group_id": "mg-…", "name": "…", "channel_type": "slack",
         "instance": "slack", "platform_id": "…", "is_group": true, "engage_mode": "pattern",
         "engage_pattern": "…", "sender_scope": "all", "ignored_message_policy": "drop",
         "unknown_sender_policy": "decline_notify", "session_mode": "…", "priority": 0,
         "threads": null, "denied_at": null}
      ],
      "destinations": [{"local_name": "…", "display_name": "…", "channel_type": "slack",
                        "target_type": "channel", "target_id": "…", "target_name": "…",
                        "created_at": "…"}],
      "sessions": {"total": 6, "running": 1},
      "tasks": {"total": 4, "paused": 2, "overdue_on_resume": 2}
    }
  ],
  "unwired_channels": [{"id": "mg-…", "name": "…", "channel_type": "slack", "instance": "slack",
                        "platform_id": "…", "unknown_sender_policy": "…", "denied_at": null}],
  "sources": {"broker": {"ok": true, "errors": {}}}
}
```

`config` is `null` when that group's `groups-config-get` failed. `target_name` is the messaging
group's or agent group's name for `target_id`, `null` if neither is known. An MCP server shows only its
name, type, transport, the broker-reduced `url` (`scheme://host[:port]`), a plain-path `command`
(the broker masks anything else), the *names* of its headers and env variables, and how many
args it has; their values never leave the console, even if the broker sent them.

**`/api/permissions`**

```json
{
  "generated_at": "…",
  "roles": [{"user_id": "slack-…", "user_name": "…", "user_kind": "slack", "role": "owner",
             "scope": "global", "group": null, "granted_at": "…", "granted_by": null}],
  "members": [{"user_id": "…", "user_name": "…", "user_kind": "slack",
               "group": {"id": "ag-…", "name": "…"}, "added_at": "…", "added_by": "…"}],
  "policies": ["<row as the broker gives it>"],
  "destinations": [{"group": {"id": "…", "name": "…"}, "local_name": "…", "display_name": "…",
                    "channel_type": "slack", "target_type": "channel", "target_id": "…",
                    "target_name": "…", "created_at": "…"}],
  "mount_allowlist": {"available": true,
                      "allowed_roots": [{"path": "/srv/…", "read_write": false, "description": "…"}],
                      "blocked_patterns": [".ssh"], "non_main_read_only": true},
  "approvals": [{"id": "appr-…", "action": "cli_command", "title": "…", "status": "pending",
                 "created_at": "…", "expires_at": null, "age_days": 147, "stale": true,
                 "group": null, "session_id": "sess-…"}],
  "not_visible": [{"what": "Per-group environment variables", "why": "…"}],
  "sources": {"broker": {"ok": true, "errors": {}}}
}
```

A role's `scope` is `global` when it has no agent group. `mount_allowlist` is `{"available":
false, "reason": "not_readable" | "broker_error"}` when the broker could not read the file or the
read failed. An approval is `stale` when it is pending and older than 7 days (F19). `not_visible`
always lists per-group env values, OneCLI secret assignments and egress lockdown, with why (§2
non-goals of the plan, F21).

**`/api/problems`**

```json
{
  "generated_at": "…",
  "items": [
    {"kind": "task_paused_overdue", "severity": "warning",
     "title": "documentation-summary.md is paused and overdue",
     "detail": "Resuming it runs it once straight away, then at 09:03 every day.",
     "at": "2026-05-27T07:03:00.000Z", "count": null,
     "ref": {"type": "task", "id": "task-…"}}
  ],
  "host_logs": {
    "window_hours": 24, "errors": 8, "warnings": 13, "truncated": false,
    "groups": [{"level": "ERROR", "message": "Container exited with error", "count": 3,
                "first_at": "…", "last_at": "…", "sample": "[15:07:55.404] ERROR …"}]
  },
  "sources": {"broker": {"ok": true, "errors": {}}, "loki": {"ok": true, "errors": {}}}
}
```

`host_logs` is `null` when Loki did not answer. Items are sorted by severity (`error`,
`warning`, `info`), then newest first. `ref.type` is `task`, `group`, `approval`, `channel` or
`source`. The kinds:

| Kind                   | Severity | When                                                              |
| ---------------------- | -------- | ----------------------------------------------------------------- |
| `source_unavailable`   | error    | A broker or Loki read failed (or `LOKI_URL` is unset); one per source |
| `claude_failing`       | error    | Claude status `failing` (§4.4)                                     |
| `claude_degraded`      | warning  | Claude status `degraded`                                           |
| `claude_unknown`       | info     | Claude status `unknown`                                            |
| `claude_auth_failures` | error / warning | 401 or 403 from Anthropic in 24 h; error if one was in the last hour |
| `nanoclaw_not_answering` | error  | NanoClaw's `/health` did not answer                                |
| `nanoclaw_unhealthy`   | error    | `/health` says `healthy: false`                                    |
| `channel_disconnected` | error    | A channel in `/health` is not connected                            |
| `message_loop_stopped` | error    | `/health` says the message loop is not running                     |
| `host_log_errors`      | error    | NanoClaw logged errors in 24 h                                     |
| `host_log_warnings`    | warning  | NanoClaw logged warnings in 24 h                                   |
| `task_paused_overdue`  | warning  | A paused task would run at once on resume (F9)                     |
| `task_failures`        | warning  | A task has failed runs                                             |
| `approval_stale`       | warning  | A pending approval older than 7 days (F19)                         |
| `dropped_messages`     | info     | Messages NanoClaw dropped (no agent wired, denied sender, …)       |

The overview's `warnings` are the same items.

## 5. The web app

`web/` is a Vue 3 single-page app on the design system (`brand/design-system/`, D9). It reads only
the console's own API (§4.7), on the page's origin, so the Access cookie rides along.

### 5.1 Shell and routes

| Path          | Page                                   | Reads              |
| ------------- | -------------------------------------- | ------------------ |
| `/`           | Overview (`views/OverviewPage.vue`)    | `/api/overview`    |
| `/tasks`      | Scheduled tasks (`views/TasksPage.vue`) | `/api/tasks`       |
| `/tasks/:id`  | One task (`views/TaskPage.vue`)        | `/api/tasks/{id}`  |
| anything else | Page not found                         | nothing            |

- **Real paths, not hashes** (`vue-router`, HTML5 history): the API serves `index.html` for any path
  it does not own (§4.7).
- **The shell** (`App.vue`) is a skip link, the Header card (product name and the page
  navigation) and the page. The navigation is the list in `src/lib/nav.ts`; a route's
  `meta.nav` names the entry it belongs to, so a task's page keeps Tasks underlined. W9 adds
  Groups, Permissions and Problems as three entries there and three routes in `src/router.ts`.
- **Every page** has one `h1` (`display`), an answer line in `body-large`, then PageStatus, then
  its content. The tab title is `<page> · NanoClaw console`.
- **Release 2** (W15) adds pause, resume and run to the task page's header, which already lays the
  title out with room at its right, and restart to W9's group page. Release 1 has no buttons.

### 5.2 Refresh and freshness

- `useApi(path)` (`src/composables/useApi.ts`) loads at once, then every 30 s while the page is
  open, and again at once when the path changes (another task). The backend and the broker cache,
  so open tabs cost NanoClaw little (F12).
- **A failed refresh keeps the last answer** and says so in a Banner ("Couldn’t reach the
  console’s API, so this page shows what it had at 15:30 CET. It retries every 30 seconds."). A
  401 or 403 says the Access sign-in may have ended and asks for a reload. There is no Retry
  button: the page retries itself.
- **The freshness line** comes from the answer's `generated_at`. **Every failed read** in
  `sources` is named in words with its code, so an empty card never looks like "none".
- An answer for a path the page has already left is dropped.

### 5.3 Times and words

- Every time is shown in **Europe/Amsterdam with the zone named** (`src/lib/time.ts`), whatever
  the browser's zone: "today at 09:03 CET", "26 May at 09:03 CEST", with a relative phrase where
  it helps ("in two hours", "five months ago"). The exact time with seconds is in each `<time>`'s
  `datetime` and tooltip.
- **A task's name** (`src/lib/tasks.ts`) is its task file without `.md`, else the start of its
  prompt cut at a word, else its id. Its status is in words; a paused task that would run at once
  on resume reads exactly "Paused — will run once immediately if resumed" (F9).
- **Claude's status** is a StatusMark (a dot and the word: OK, Degraded, Failing, Unknown; B2,
  B26), never colour alone. The quota is labelled with the API's `quota.label` verbatim (D6).

### 5.4 Task files

A task file ("what it will do") is written by an agent inside its container, so it is untrusted.
`src/lib/markdown.ts` renders it with `marked`, then sanitises it with DOMPurify before it reaches
`v-html`: only text tags (headings, paragraphs, lists, emphasis, code, quotes, rules, tables and
links), links to `http`, `https` and `mailto` only with `rel="noopener noreferrer"`, and no images,
forms, frames, styles or scripts. Headings move down two levels, under the page's own. The prompt
and the run log are plain text.

### 5.5 Layout

- One column on a phone with 16 px gutters; nothing scrolls sideways at 390 px. The overview's
  four cards sit two across from 1024 px.
- **The task list** is a table from 1024 px and a card per task below it (TaskList card). Both are
  in the page and only one is displayed; rows have the id `task-row-<series id>` and cards
  `task-card-<series id>`.
- **Stable ids** mark everything a test or a person might point at: `#claude-status` (with
  `data-status`), `#claude-reasons`, `#claude-last-success`, `#claude-auth-failures`,
  `#claude-probe`, `#nanoclaw-card`, `#nanoclaw-not-answering`, `#quota-label`, `#quota-used`,
  `#count-*`, `#warnings`, `#page-banner`, `#page-freshness`, `#page-sources`, `#tasks-table`,
  `#tasks-cards`, `#task-overdue`, `#task-file-content`, `#task-prompt`, `#task-run-log`, and the
  header's `#nav-<page>`.

### 5.6 Tests

- **Vitest** (`src/**/__tests__/`): the libraries, the refresh composable with fake timers, each
  card, and each page mounted with its route and `fetch` stubbed. Coverage floors are 95 %.
- **Playwright** (`e2e/`): axe at WCAG 2.2 AA plus best practice on every page in light and dark
  at 1440 px and 390 px, no sideways scroll, and what each page shows, against the production
  build with `/api` mocked.
- Both use the mock answers in `src/fixtures/api.ts`, shaped exactly as §4.7 and including the
  paused documentation-summary task with `overdue_on_resume: true` and a task file with a planted
  script, image and `javascript:` link.

## 6. Repository layout

| Path                     | What                                                               |
| ------------------------ | ------------------------------------------------------------------ |
| `api/`                   | uv project `nanoclaw-console-api`: the FastAPI app                 |
| `broker/`                | uv project `nanoclaw-console-broker`: the broker, stdlib only      |
| `web/`                   | Vue 3, Vite, Tailwind v4, vue-router, reka-ui, Pinia (§5)         |
| `brand/design-system/`   | The design system's source and its gate settings (`checks.json`)   |
| `scripts/`               | The design system's gate and token generator (stdlib Python)       |
| `Dockerfile`             | The console image: builds `web/`, then installs `api/` beside it   |
| `broker/Dockerfile`      | The broker image                                                   |
