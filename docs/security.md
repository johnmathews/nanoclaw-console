# Security model

**Status:** current, checked live on 2026-11-08 (release 1 and release 2).

The console shows NanoClaw's state and offers four small actions. NanoClaw's control socket
(`data/ncl.sock`) checks no caller and can do anything: grant roles, rewrite mounts, wire secrets,
and through task scripts and mounts reach the host. So this console is built around one question:
what can someone do if they get past a given layer? [architecture.md](architecture.md) has the
mechanisms; this page says what each one protects, and what is accepted.

## 1. What is protected, and from whom

```
+-----------------------------------+--------------------------------------------------------------+
| Asset                             | Threat                                                       |
+-----------------------------------+--------------------------------------------------------------+
| ncl.sock (full NanoClaw control)  | Anyone who can send it a frame, including a bad console      |
|                                   |   image or a bug in the console                              |
| Secrets inside ncl's answers      | MCP bearer tokens in groups-config-get, URLs with webhook    |
|                                   |   secrets in the path, Bearer values in task prompts and logs|
| The four actions                  | A cross-site page in John's browser (CSRF), a forged or      |
|                                   |   other-app Access token, a double click                     |
| The host                          | NanoClaw's own agent containers on the same LXC, the LAN and |
|                                   |   the tailnet reaching the console port                      |
+-----------------------------------+--------------------------------------------------------------+
```

Agents are untrusted: they write task files, prompts and run logs, so all of that is treated as
hostile input.

## 2. The layers, outermost first

1. **Cloudflare Access**, enforced at the edge and again by cloudflared (`access_aud` on the
   ingress rule). Only John's email gets a token. A cross-site request carries no Access cookie,
   so it stops here (checked live: a forged POST from another origin never reached the console).
2. **The host firewall** admits the console port from cloudflared and Gatus only. The LAN, the
   tailnet and every container on the LXC, NanoClaw's agents included, are dropped.
3. **The console's own Access check** on every route but `/healthz`: RS256, audience, issuer,
   `type: app`, email allowlist; it fails closed when unconfigured ([architecture.md
   §4.2](architecture.md)). A JWT from another Access app is refused.
4. **The action guard**: `X-Console-Action: 1`, exact `Origin`, `Sec-Fetch-Site: same-origin`,
   JSON content type, a `{}` body read with a 1 KiB cap, and the id pattern
   ([§4.8](architecture.md)). Each refusal is audited with its reason. This guard matters only if
   layer 1 is ever bypassed, for example by a later Access Bypass policy.
5. **The broker: the security boundary.** It is the only process that can open `ncl.sock`. The
   console sends a verb name and ids; the broker builds every ncl frame itself from a fixed list
   of 20 reads and exactly four writes (`tasks-pause`, `tasks-resume`, `tasks-run`,
   `groups-restart`), each taking one id. Nothing the console sends can widen that list
   ([§3.4, §3.9](architecture.md)).
6. **Redaction on the host, before caching** ([§3.5](architecture.md)): headers and env values,
   URL paths and userinfo, `Bearer` values, task scripts and approval payloads never leave the
   broker. ncl's error text goes only to the broker's log.

Below the broker, the mounts are read-only, both images run as non-root with a read-only root
filesystem, no capabilities and no new privileges, and the console container has no NanoClaw path
at all: only the broker's socket directory.

## 3. What a compromise of each piece gives

```
+-------------------------------+-----------------------------------------------------------------+
| If this is compromised        | The attacker gets                                               |
+-------------------------------+-----------------------------------------------------------------+
| John's Access session         | What John can do in the console: read redacted state, the four  |
|                               |   actions. Each action is audited with the email and cf_ray     |
| The console image or process  | The broker's verb list, nothing more: redacted reads and the    |
|                               |   four id-only actions. No secret, no grant, no mount, no host  |
| The broker image              | ncl.sock, so all of NanoClaw. This is why the broker is pinned  |
|                               |   and upgraded by hand after review, never auto-deployed        |
| An agent writing hostile text | Rendered text only: task files are sanitised Markdown, opened   |
|   (task file, prompt, log)    |   with O_NOFOLLOW and capped at 256 KiB                         |
+-------------------------------+-----------------------------------------------------------------+
```

## 4. The deployment tradeoff

The console's `latest` is auto-deployed by WUD within about a minute of a green `main`, while the
broker is pinned to a `sha-` tag and moved only by `make nanoclaw-broker-upgrade` in proxmox-setup.

That split is the point. A bad console image reaches at most the broker's verb list (§3), so it can
move as fast as John's other apps, on the same trust: images publish only after CI passes on
`main` ([development.md](development.md)). The broker holds the socket, so a change to it waits for
a reviewed merge and a deliberate pin. Accepted in the security review of 2026-11-08.

To freeze the console, the host role pins its tag and turns WUD off (proxmox-setup,
`documentation/nanoclaw-console.md` §5).

## 5. Accepted risks and follow-ups

- **The broker is pinned by tag, not by digest.** Anyone who could push to ghcr could replace
  `sha-<short>`. The same publish rights could change `main`, so a digest pin adds little today (#5).
- **A hard kill mid-action leaves no audit line in the file.** An exit or exception is recorded as
  `interrupted` or `error`; a SIGKILL between the broker acting and the write is not. The broker's
  own request log still has the verb and id (B52, #3).
- **"Run now" has no cooldown.** It spends Claude tokens on each run; a second click while one is in
  flight is a 409, but one after it finishes runs again (#4).
- **The audit write `fsync`s on the event loop.** It can stall other requests briefly, but only
  after the Access check and the allowlist pass, so only John can cause it (#10).

The other hardening follow-ups are a CSP header (#6) and digest-pinned base images (#5).

## 6. How it was checked

- **Unit and contract tests:** the verb allowlist (no frame outside it can be built), redaction of
  every field shape, the Access check's refusals, and each action-guard rule. `make ci` runs them.
- **Live, release 1:** counts matched `ncl`; no secret appeared in any reply (compared by hash);
  every path but the tunnel was refused; a forged JWT got 403.
- **Live, release 2:** pause and resume flipped the status without moving the next run; restarting an
  idle group answered `{restarted: 0}`; a cross-site POST never arrived; signed-in requests breaking
  one guard rule each got 403 (a bad id 404); every attempt left one audit line.
