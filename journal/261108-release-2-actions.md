# 2026-11-08 — Release 2: pause, resume, run task and restart group

The console can now change NanoClaw in exactly four ways: pause, resume or run a task, and
restart a group. Each is a button that opens a confirmation, a `POST` behind a CSRF guard, and a
line in an append-only audit log. This is unit W15 of the engineering-team run
`manual-20261108T121535Z` in proxmox-setup, on branch `eng-nanoclaw-console-r2` from `c128faf`
(release 1, live). The design is [docs/architecture.md](../docs/architecture.md) §3.9, §4.8,
§4.9 and §5.8; the choices are B42–B51 in [docs/decisions.md](../docs/decisions.md). Not
deployed: nothing here ran a write against the live NanoClaw.

## What NanoClaw actually does (read on the host, `479a9510`)

- `tasks pause` / `resume` (`src/cli/resources/tasks.ts:617-643`, `mutateTask` `:267-279`) flip
  every pending (or paused) row of the series in an active session and leave `process_after`
  alone, so resuming an overdue task fires it at the next sweep. They answer `{series_id,
  touched}`, or `handler-error` "no live task matched: <id>", which covers three different
  situations: a repeat, a task running right now, and no such task.
- `tasks run` (`:377-406`) inserts an extra pending row due now with no recurrence: one run, the
  schedule unchanged, and not idempotent. `{series_id, row_id, status}`, or "task not found".
- `groups restart` (`groups.ts:326-388`) kills the group's running containers and respawns those
  with messages waiting. It answers `{restarted: 0, rebuilt: false}` for a group that does not
  exist, and its `approval` access does not apply to a host caller.

## What was built

- **Broker:** the four writes in the frozen registry (`write=True`, `cacheable=False`, id only,
  no fixed args). "No live task matched" is settled with one fresh `tasks-get` into
  `already_in_state`, `not_found` or `no_live_run`; ncl's text is still never sent on. After a
  write the cached reads it can change are dropped, and a read already in flight is not stored.
- **API:** `POST /api/tasks/{id}/pause|resume|run` and `POST /api/groups/{id}/restart`. The guard
  wants `X-Console-Action: 1`, `Origin` equal to `CONSOLE_ORIGIN`, `Sec-Fetch-Site: same-origin`,
  JSON and a body of `{}`. The audit file is opened before the broker is asked, so an unwritable
  `AUDIT_DIR` means 503 and nothing done. `GET /api/audit` serves the last 200 lines, shaped
  field by field. A second identical request while one runs is `409 busy`; a restart checks the
  group exists first.
- **Web:** secondary buttons beside the task and group headings, a ConfirmDialog on Reka's
  AlertDialog (the thing, its state now, what happens, the plan's caution, Cancel focused), the
  answer under the heading after a refresh, and an Audit page in the navigation.
- **Design system:** Button and ConfirmDialog rewritten in the console's words, Header at six
  pages, and a new AuditList card. No new tokens, no mockup (B50). The gate passes `--complete`;
  every card renders at 375 px without overflow.
- **Image:** `/var/lib/nanoclaw-console/audit` ships empty, 10001:10001, 0700, so a new named
  volume starts writable on the read-only root. `compose-smoke` now proves it.

## Seen red first

- Broker: 96 failures before the change (the writes answered `unknown_verb`; `ReadCache` had no
  `invalidate`). One more after: a cache test showed a load scheduled before an invalidation but
  started after it was still stored, because the generation was read when the task first ran.
  The generation is now taken when the load is scheduled.
- API: every test errored on `Settings` lacking `console_origin`, and `nanoclaw_console.audit`
  did not exist.
- Web: the dialog's `aria-labelledby` pointed at nothing, because an `id` on the title overrode
  Reka's own (the test asked the label's element for its text and got `undefined`). And the
  screenshots showed "Asking the console's API…" under a loaded task: the result message had been
  inserted inside the page's `v-if` chain. A load-time assertion now catches it, seen red against
  the old template before the fix.
- `compose-smoke` first failed on the volume's mode (0755 from a plain `COPY --chown`);
  `--chmod=0700` fixed it.

## Not done here, and why

- **Deploying:** the infra repo needs the broker pin moved to this branch's `sha-…` after merge,
  the audit volume and `AUDIT_DIR` / `CONSOLE_ORIGIN` in the console's compose. Until then the
  merged console (auto-deployed by WUD) fails safe: with the old broker every action answers
  "the broker doesn't offer this action", and without the volume the read-only root makes every
  action a 503.
- **Live verification** is W16, with John's go-ahead: pause and resume a far-off task, restart an
  idle group, a forged cross-site POST, and the audit log.
