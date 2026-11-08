# NanoClaw console

A web console for NanoClaw v2 as it runs on John's home
server. It answers: is Claude working, which groups and channels exist and what may they do, which
scheduled tasks run and when, which permissions are in place, and what has gone wrong. Release 1 is
read-only; release 2 adds pause, resume and run for a task and restart for a group, each behind a
confirmation and an audit log.

It is deployed by Ansible from
[proxmox-setup](https://github.com/johnmathews/home-server) to the agent LXC, behind Cloudflare
Access at `nanoclaw.itsa-pizza.com`. It never changes the NanoClaw fork.

**Status:** release 1 is live at `nanoclaw.itsa-pizza.com` (deployed 2026-11-08): the broker
(read verbs, redaction, cache), the API (Access check, every view) and the five views (overview,
scheduled tasks, groups and channels, permissions, problems). Release 2 is built and passes
`make ci`, not yet deployed: pause, resume and run for a task and restart for a group, each behind
a confirmation dialog, a CSRF guard and an append-only audit log, and an audit page. Its deployment
needs a newer broker pin and an audit volume in proxmox-setup's `agent_lxc` role, then a live check
with John's go-ahead.

## 1. How it fits together

Two images, both built here:

- **`nanoclaw-console-broker`**: the only process that talks to NanoClaw's control socket. A fixed
  verb list (reads, and exactly four writes that take an id and nothing else), redaction and a
  cache. No port.
- **`nanoclaw-console`**: FastAPI serving the JSON API and the Vue app. It reaches NanoClaw only
  through the broker.

[docs/architecture.md](docs/architecture.md) has the detail and [docs/decisions.md](docs/decisions.md)
the reasons.

## 2. Run it locally

Needs uv, Node 22 and Docker.

```sh
make install                      # uv sync for api/ and broker/, npm ci for web/
make ci                           # lint, typecheck, unit tests, e2e, design-system gate

cd api && uv run uvicorn --factory nanoclaw_console.app:create_app_from_env --port 8000
cd web && npm run dev             # http://localhost:5173, proxies /api to :8000
```

Or the production shape: `make build` builds both images, and `make compose-smoke` starts the console
image hardened as deployed and checks `/healthz`.

[docs/development.md](docs/development.md) covers the toolchain, every make target, local CI and the
design system.
