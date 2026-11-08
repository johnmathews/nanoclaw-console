# NanoClaw console

A web console for NanoClaw v2 on the home server's agent LXC: Claude health, groups and channels,
scheduled tasks, permissions, errors and warnings. Read [docs/architecture.md](docs/architecture.md)
first, [docs/security.md](docs/security.md) for what each layer protects, and
[docs/decisions.md](docs/decisions.md) for why.

**Stack:** `api/` FastAPI on Python 3.13 with uv; `broker/` stdlib-only Python 3.13 with uv;
`web/` Vue 3, Vite, Tailwind v4, reka-ui, Pinia. Two images: the console (`Dockerfile`) and the
broker (`broker/Dockerfile`). Make targets: [docs/development.md](docs/development.md) §2.

**The broker is the security boundary.** It is the only process that opens NanoClaw's `ncl.sock`,
and its fixed verb list is what limits the console. The console holds no NanoClaw access of its own;
never give it the socket, `data/`, `groups/` or `.env`. Never add a NanoClaw write verb outside the
documented list: since release 2 the broker has exactly four writes, `tasks-pause`, `tasks-resume`,
`tasks-run` and `groups-restart`, each with `--id` only (decision D4). Anything else stays in `ncl`.

**Never touch the NanoClaw fork** (D1). This repo reads NanoClaw from outside.

**CI is local.** Run `make ci` before every push. Once it has passed, put `[skip ci]` in the commit
message. A push to `main` that should publish images needs GitHub's CI to run: its success is what
lets `docker.yml` publish, and the console's `latest` auto-deploys.

**UI follows the design system** in `brand/design-system/` (tracker's, reused: D9). Use the
design-system skill, build from the tokens and cards, and add or rewrite a card in the system before
a screen uses it. A visual change starts as a mockup in `brand/design-system/mockups/` and waits for
John's pick. Never show a secret value on screen; show that it exists.

Every session that changes something adds a dated entry to `journal/` (`yymmdd-name.md`), and
`docs/` stays current.

## Shipping

- **Lands by:** pull request, squash-merged once `check` is green. The squash message must not contain
  `[skip ci]`: CI on `main` is what lets `docker.yml` publish.
- **CI runs locally** (`make ci`); branch commits carry `[skip ci]` once it has passed.
- **Environments:** one, the agent LXC, deployed from proxmox-setup.
  - The console: WUD redeploys `latest` within about a minute of the publish and pushes "NanoClaw console
    updated". Check: `ssh agent 'cd /srv/apps/nanoclaw-console && docker compose ps'`.
  - The broker: pinned, never auto-deployed. In proxmox-setup, `make nanoclaw-broker-upgrade V=sha-<short>`,
    then commit the pin there. A broker change is not live until that runs.
  - A change that needs new host config (env, volume, mount) lands in proxmox-setup's `agent_lxc` role, and
    its order against the console merge matters (`documentation/nanoclaw-console.md` there).
