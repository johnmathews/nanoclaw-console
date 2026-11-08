# Decisions

> Purpose
>
> Why the console is built the way it is. These are the decisions taken with John on 2026-11-08,
> when the console was planned (proxmox-setup, engineering-team run `manual-20261108T121535Z`). That
> plan is a working file; this page is the record that outlives it. Journals and pull requests cite
> these IDs.

## 1. The decisions

| ID  | Decision | Why |
| --- | -------- | --- |
| D1  | **Off trunk.** The console lives in its own repo, `johnmathews/nanoclaw-console`, and never imports or edits the NanoClaw fork. Its only coupling is `ncl.sock`'s frame format. | `/update-nanoclaw` must keep merging upstream without a UI in the way. |
| D2  | **A broker holds the authority.** Two images: the broker (uid 1000, host networking, no port, `data/` and `groups/` read-only) builds every `ncl` frame from a fixed verb list, redacts and caches; the console (FastAPI and Vue) holds only the broker's socket, runs as a non-1000 uid on a read-only rootfs and auto-deploys. The broker's verb list is the security boundary. | `ncl.sock` grants full control of NanoClaw, and through task scripts and mounts a route to root on the host, to anything that opens it; a web app on a public hostname must never hold it. |
| D3  | **Access.** A dedicated Cloudflare Access app (own AUD, John's email only); the app validates the JWT itself with its own email allowlist; the port is bound to `192.168.2.107` and a firewall rule admits only cloudflared (`192.168.2.101`). | A shared wildcard Access app would let a JWT from any other protected app open the console. |
| D4  | **Read-only first.** Release 1 has no write verbs. Release 2 adds exactly `tasks-pause`, `tasks-resume`, `tasks-run` and `groups-restart`, each taking `--id` only, behind a confirmation and an audit log. Grants, deletes, mounts and edits stay in `ncl`. | Only small, reversible actions are worth a web button; everything else is safer typed. |
| D5  | **Fix OneCLI's open API first.** The unauthenticated OneCLI API on port 10254 is closed to every container before any console container exists. | A new container on the host must not be able to reach it. |
| D6  | **Claude health comes from OneCLI's traffic**, never from `ncl usage` alone; `usage` is shown as the host login's quota, labelled as such. | `ncl usage` measures the host's `~/.claude` login, not the token NanoClaw's agents use. |
| D7  | **Template: tracker**, collapsed to one app image on library's pattern plus the broker image, amd64 only. CI runs locally (`make ci`); GitHub keeps one lean job that gates the ghcr publish. | The same stack as John's other apps; WUD needs a published `latest`, and Actions minutes cost money. |
| D8  | **Port 8002** on `192.168.2.107`. | Free on the live host when it was checked. |
| D9  | **Look: tracker's design system**, reused with its checks and renamed for the console; no new brand session. | John's choice: his home-server apps look like one family. |
| D10 | **The repo is public.** | WUD then reads ghcr anonymously; a private repo needs a ghcr token on the host. |
| D11 | **Two PRs, in order:** this repo's release-1 PR merges first (its merge publishes the images), then proxmox-setup's deploy PR after live verification; release 2 is a second PR here. | The deploy needs published images, and verification needs the deploy. |

## 2. Made while building

| ID  | Decision | Why |
| --- | -------- | --- |
| B1  | The design system keeps tracker's token values and the generic cards (13 of 40); tracker's planner, notes, Ask, email and settings cards and its wordmark were left out. The carried-over cards keep tracker's sample copy until the console first uses each one. | D9 asks for the look, not tracker's product screens; rewriting cards before a screen needs them would be guessing. |
| B2  | The three pens mean OK, degraded and failing, always beside words. | Tracker's green, yellow and red markers map onto a status without new colours; `pen-partial` is too faint for text, so the words carry the meaning. |
| B3  | The theme follows the OS (`prefers-color-scheme`); there is no theme setting. | A one-person console needs no settings page yet. |
| B4  | `/healthz` sits outside `/api/` and returns only `{"ok": true}`, with no auth. | It is the container healthcheck, and must say nothing about NanoClaw to whoever can reach the port. |
| B5  | Broker ids match `^[A-Za-z0-9][A-Za-z0-9-]{0,79}$`: the run plan's pattern, tightened so an id cannot start with `-`. | An id like `--script` is harmless in a JSON frame, but refusing it at the boundary costs nothing; every live group and task id matches. |
| B6  | A redacted URL keeps only `scheme://host[:port]`; the path goes with the userinfo, query and fragment. | Paths carry secrets too (Home Assistant's MCP webhook is `/api/webhook/mcp_<secret>/…`), and the UI needs only the host. |
| B7  | MCP server entries are allowlisted: `type`, `transport`, a reduced `url`, a plain-path `command`, and header and env names; `args` items and any other field are masked. | stdio servers take tokens as arguments, and a field NanoClaw adds later must stay hidden until someone decides it is safe. |
| B8  | `groups-config-get` returns only the 16 keys NanoClaw's `presentConfig` has today; other top-level keys are dropped. | An `env` block or a new secret-bearing field upstream is dropped by default instead of shown. |
| B9  | Broker errors are not cached. | Single-flight and the cap of 2 calls in flight already bound the load a failing verb causes, and a cached error would hide NanoClaw coming back. |
| B10 | The broker never forwards ncl's `human` field, only `data`. | `human` is server-rendered text; it could repeat what redaction removes from `data`. |
