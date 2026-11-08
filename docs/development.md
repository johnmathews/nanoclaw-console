# Development

> Purpose
>
> How to work on the console: the toolchain, the make targets, running it locally, the local CI
> that runs before every push, and the design system's gate.

## 1. Toolchain

- **Python 3.13 with uv** for `api/` and `broker/`, two separate uv projects with their own
  `uv.lock`. ruff (tracker's rule set), mypy `--strict`, pytest with branch coverage and a 95 %
  floor (`fail_under` in each `pyproject.toml`).
- **The broker is standard library only** at runtime. A dependency there is attack surface on the
  one process that holds NanoClaw's authority, so adding one needs a reason in
  [decisions.md](decisions.md).
- **Node 22 and npm 11** for `web/`. npm 10.9, which ships with Node 22, crashes resolving this
  dependency tree (`Cannot read properties of null (reading 'edgesOut')`), so the make targets run
  `npx -y npm@11`. The tree and its lockfile were copied from tracker.
- **The web stack:** Vue 3.5, vue-router 5, Pinia, Vite 8, Tailwind CSS 4, reka-ui, marked 18 and
  DOMPurify 3 (task files, B28), TypeScript 6, Vitest 4 with
  jsdom and v8 coverage (95 % floors in `vitest.config.ts`), Playwright with `@axe-core/playwright`,
  oxlint and ESLint (with the Tailwind and template-accessibility rules), Prettier.
- **Docker** to build the two images and run `make compose-smoke`.

## 2. Make targets

`make help` lists them. All run from the repo root.

| Target          | What it does                                                                  |
| --------------- | ----------------------------------------------------------------------------- |
| `install`       | `uv sync --locked` in `api/` and `broker/`; `npm ci` in `web/`                |
| `lint`          | ruff check and format check; oxlint, ESLint and Prettier's check              |
| `typecheck`     | mypy on both Python projects; `vue-tsc --build` on `web/`                     |
| `test`          | pytest under coverage on both Python projects; Vitest with coverage           |
| `e2e`           | Playwright and axe against `vite preview` of the production build, `/api` mocked |
| `design-check`  | The design system's gate (`--complete`) and the freshness of `tokens.css`     |
| `ci`            | `lint`, `typecheck`, `test`, `e2e`, `design-check`, in that order, stopping at the first failure |
| `build`         | Both images for `linux/amd64`, tagged `nanoclaw-console:local` and `nanoclaw-console-broker:local` |
| `compose-smoke` | Builds the app image, starts it hardened as deployed (read-only root, no capabilities, uid 10001) and checks `/healthz`, the page and a 404 |

## 3. Local CI first

GitHub Actions costs money, so the full suite runs on your machine:

1. `make ci` before every push. It is the only place e2e runs.
2. Once it has passed, put `[skip ci]` in the commit message, unless the push is to `main` and
   should publish images (below).
3. GitHub keeps one lean job (`.github/workflows/ci.yml`: install, lint, typecheck, unit tests and
   the design gate). It exists because a green run of it on `main` is what lets
   `.github/workflows/docker.yml` publish.

**Publishing.** `docker.yml` runs when CI completes on `main`, and only if it succeeded on a push.
It builds the exact commit CI passed (`head_sha`), for amd64, and pushes
`ghcr.io/johnmathews/nanoclaw-console` and `ghcr.io/johnmathews/nanoclaw-console-broker`, each tagged
`latest` and `sha-<7 chars>` and labelled `org.opencontainers.image.revision`. It can also be run by
hand on `main` (`workflow_dispatch`). The console's `latest` is auto-deployed on the agent LXC, so a
commit on `main` is a deploy. The broker is pinned by SHA there and is upgraded deliberately.

## 4. Running it locally

```sh
make install
cd api && uv run uvicorn --factory nanoclaw_console.app:create_app_from_env --port 8000
cd web && npm run dev
```

The dev server on <http://localhost:5173> forwards `/api` and `/healthz` to `127.0.0.1:8000`
(`API_URL` overrides it). Without a `STATIC_DIR` the API serves only its routes, which is what you
want with Vite in front. To see the production shape instead, `make build-app` and run the image, or
`make compose-smoke`.

The broker needs a NanoClaw `ncl.sock`, which only exists on the agent host. Locally, its tests
run it against a fake ncl server that replays frames captured from the host
(`broker/tests/fixtures/`). To run it by hand against any socket:

```sh
cd broker && uv run python -m nanoclaw_broker --socket /tmp/b.sock --ncl-socket /path/to/ncl.sock
printf '%s\n' '{"verb": "groups-list"}' | nc -U /tmp/b.sock
```

Its options and protocol are in [architecture.md](architecture.md) §3.

## 5. The design system

The look is tracker's design system, reused (decision D9). Its source is
`brand/design-system/project/` (`tokens.json`, `foundations.md`, `voice.md` and a card per
component); `checks.json` sets the gate. Rules:

- Build from the tokens and the cards. A new component, or the first console use of a carried-over
  card, starts as a card in the system (preview and README) before it reaches `web/`.
- `web/src/styles/tokens.css` is generated: change `tokens.json`, then `npm run tokens` in `web/`.
  `make design-check` fails on a hand edit or a stale file.
- Tailwind's default palette is off (`web/src/styles/main.css`): a colour comes from a role
  (`bg-canvas`, `text-ink-secondary`), and ESLint refuses arbitrary colours.
- `python3 scripts/design_preview.py brand/design-system` writes an offline gallery to
  `brand/design-system/preview/` (git-ignored).

## 6. Tests

- `api/tests/`, `broker/tests/`: pytest. Each Python project's coverage floor is in its
  `pyproject.toml`. The broker's async tests use `pytest-asyncio` (dev only; the image stays
  standard library).
- **Broker fixtures** (`broker/tests/fixtures/`): `ncl_frames.json` holds real replies from the
  host, scrubbed on the host before they were printed (free text is lorem ipsum, ids are fixture
  ids), with fake secrets planted (every one contains `PLANTED-SECRET`). `ncl_commands.json` is
  every registered ncl command. Recapture both after a NanoClaw update that changes the CLI; never
  copy a raw `groups config get` reply off the host, because it carries live bearer tokens.
- `web/src/**/__tests__/`: Vitest component and store tests, with `fetch` stubbed.
- `web/e2e/`: Playwright. `support.ts` opens the app in a theme with `/api` mocked through
  `page.route`, runs axe at WCAG 2.2 AA plus best practice, and checks for sideways scroll. The
  suite runs at 1440 px and 390 px, in light and dark.
- **The secret-absence test** (`web/src/__tests__/secrets.spec.ts`, and the last test in
  `web/e2e/w9.spec.ts`): the web fixtures plant `Bearer PLANTED-SECRET-…` in keys the contract
  does not have, and no page may carry it ([architecture.md](architecture.md) §5.7). A new page
  goes into both lists of pages there.

## 7. Configuration

The console reads its settings from the environment at start ([architecture.md](architecture.md)
§4). The deployment (proxmox-setup's `agent_lxc` role) sets them; locally, set them by hand.

| Variable             | Default                              | What                                                                     |
| -------------------- | ------------------------------------ | ------------------------------------------------------------------------ |
| `ACCESS_TEAM_DOMAIN` | none                                 | The Access team's host, `<team>.cloudflareaccess.com`; its keys sign the JWT |
| `ACCESS_AUD`         | none                                 | The console's own Access application audience tag (D3)                   |
| `ALLOWED_EMAILS`     | none                                 | Who may use the console: emails separated by commas or spaces, any case  |
| `LOKI_URL`           | none                                 | Loki's base URL, `http://192.168.2.106:3100` on the LAN                  |
| `BROKER_SOCKET`      | `/run/nanoclaw-console/broker.sock`  | The broker's Unix socket                                                 |
| `NANOCLAW_TIMEZONE`  | `Europe/Amsterdam`                   | The zone NanoClaw evaluates task cron in (an IANA name)                  |
| `STATIC_DIR`         | `/app/static`                        | The built web app; ignored if the directory does not exist               |

- **The three `ACCESS_*`/`ALLOWED_EMAILS` settings fail closed.** With any of them empty, or a team
  domain that is not a bare `*.cloudflareaccess.com` host, every request except `/healthz` gets 403
  and the reason is logged once. So a console run locally without them refuses everything; to try
  the API by hand, run the tests' fixtures instead, or set the three to a test team and send a JWT
  signed with a key you serve (the tests do this, `api/tests/jwt_helpers.py`).
- **Without `LOKI_URL`** the console still serves every view; Claude's Loki signals and the host
  log groups are `null`, and `sources.loki` says `not_configured`.
- A `LOKI_URL` that is not an `http://` or `https://` URL, or a `NANOCLAW_TIMEZONE` that is not a
  known zone, stops the console at start: that is a deployment mistake, and failing loudly beats
  showing wrong times.
