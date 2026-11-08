# Architecture

> Purpose
>
> What the NanoClaw console is made of: the two images this repo builds, which of them holds
> NanoClaw's authority, how the broker guards it (verb list, redaction, cache), and the routes the
> console serves today. The console's Access JWT check is written here when it is built.

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
gives it read verbs only.

### 3.1 Modules

| Module          | Job                                                                                  |
| --------------- | ------------------------------------------------------------------------------------ |
| `ncl_client.py` | Speaks NanoClaw's frame protocol: one connection per call, one line each way         |
| `verbs.py`      | The frozen verb registry: verb name → ncl command, id parameters, fixed args          |
| `redact.py`     | Removes secrets from every reply before it is cached, logged or returned             |
| `cache.py`      | 20 s TTL per (verb, params), single-flight, at most 2 ncl calls in flight            |
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
  `ok: false`; its code and message are passed on, the message cut to 500 characters),
  `protocol_error` (ncl's reply was malformed or too large) and `internal`.

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
- SIGTERM or SIGINT closes the server, removes the socket and exits 0.
- The log is JSON lines on stdout: one `request` event per request with the verb (only a known
  verb name), the validated ids, the cache result (`hit`, `miss`, `shared`), the outcome and the
  duration. It never contains reply data.

## 4. Routes today

The scaffold serves:

- `GET /healthz`: the container healthcheck. No auth, and it returns exactly `{"ok": true}`, so it
  says nothing about NanoClaw.
- `GET /api/overview`: a placeholder that returns `{"status": "scaffold"}` until the view APIs
  land.
- Everything else: the built SPA from the static directory (`STATIC_DIR`, default `/app/static`),
  when that directory exists. An unknown path that is not under `/api/` gets `index.html`, so
  client-side routes reload. Without a static directory (local API development), only the routes
  above exist.

## 5. Repository layout

| Path                     | What                                                               |
| ------------------------ | ------------------------------------------------------------------ |
| `api/`                   | uv project `nanoclaw-console-api`: the FastAPI app                 |
| `broker/`                | uv project `nanoclaw-console-broker`: the broker, stdlib only      |
| `web/`                   | Vue 3, Vite, Tailwind v4, reka-ui, Pinia                           |
| `brand/design-system/`   | The design system's source and its gate settings (`checks.json`)   |
| `scripts/`               | The design system's gate and token generator (stdlib Python)       |
| `Dockerfile`             | The console image: builds `web/`, then installs `api/` beside it   |
| `broker/Dockerfile`      | The broker image                                                   |
