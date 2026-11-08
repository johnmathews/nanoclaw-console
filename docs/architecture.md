# Architecture

> Purpose
>
> What the NanoClaw console is made of: the two images this repo builds, which of them holds
> NanoClaw's authority, and the routes the console serves today. The full security model (Access
> JWT, the broker's verb list, redaction) is written when those parts are built; this page states
> the boundary they sit on.

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

## 3. Routes today

The scaffold serves:

- `GET /healthz`: the container healthcheck. No auth, and it returns exactly `{"ok": true}`, so it
  says nothing about NanoClaw.
- `GET /api/overview`: a placeholder that returns `{"status": "scaffold"}` until the view APIs
  land.
- Everything else: the built SPA from the static directory (`STATIC_DIR`, default `/app/static`),
  when that directory exists. An unknown path that is not under `/api/` gets `index.html`, so
  client-side routes reload. Without a static directory (local API development), only the routes
  above exist.

## 4. Repository layout

| Path                     | What                                                               |
| ------------------------ | ------------------------------------------------------------------ |
| `api/`                   | uv project `nanoclaw-console-api`: the FastAPI app                 |
| `broker/`                | uv project `nanoclaw-console-broker`: the broker, stdlib only      |
| `web/`                   | Vue 3, Vite, Tailwind v4, reka-ui, Pinia                           |
| `brand/design-system/`   | The design system's source and its gate settings (`checks.json`)   |
| `scripts/`               | The design system's gate and token generator (stdlib Python)       |
| `Dockerfile`             | The console image: builds `web/`, then installs `api/` beside it   |
| `broker/Dockerfile`      | The broker image                                                   |
