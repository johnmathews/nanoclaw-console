# 2026-11-08 — Release 2 PR wrap-up

The `/done` pass before the release-2 PR (W15) went up, on engineering-team run
`manual-20261108T121535Z`. W15's own entry is `261108-release-2-actions.md`; this one covers only
what the wrap-up found and changed.

## What the wrap-up checked

- **Local CI:** `make ci` passed on `fdef4cd` before any change (api 563, broker 618, Vitest 208,
  Playwright 82). After the fixes it passed again (api 575, broker 618, Vitest 209, Playwright
  82). `make compose-smoke` passed after the fixes.
- **Secrets:** the scan of the diff found none. The only addresses are `example.com` ones and the
  planted `PLANTED-SECRET` fixtures.
- **Docs audit:** a separate agent cross-checked the docs against the code. It found no stale
  security claim, and ten smaller gaps; nine are fixed (below). The one left is that architecture
  §4 (its opening) counts "five views and a task detail" without the audit page, which reads no broker data.
- **Security review:** a separate agent read the allowlist, the guard, the audit log, the dialogs
  and the escaping, and probed the guard with edge cases (methods, headers, content types,
  bodies, ids).
  - **Held:** the broker has exactly four writes, id only. No refusal reaches the broker. There is
    no `confirm()`, and the only `v-html` is the DOMPurify-sanitised task file from release 1.
  - **Found:** gaps in the audit log's durability (below).

## Fixed

1. **Body cap (lead).** The 1 KiB cap was checked after `request.body()` had read the whole body.
   Now a declared `Content-Length` over the cap is refused unread, and a chunked body stops being
   read once it passes the cap.
2. **Every exit from the broker call is audited (lead).** Before, an exception, or a client
   hang-up that cancelled the handler, between the broker acting and the line left no line at
   all. Now:
   - the call runs under `asyncio.shield`;
   - a cancelled request writes `interrupted`, and a second line records the call's real
     outcome when it finishes;
   - an exception writes `error`, with the type name only;
   - the busy key stays held until the shielded call finishes, so a retry cannot overlap it.
3. **The audit write itself:**
   - a short `os.write` is finished, or it raises, instead of leaving half a line;
   - each line is `fsync`ed;
   - the file is written before stdout gets its copy;
   - a broken stdout is logged and no longer stops the file line.
4. **`audit_failed` wording:** the page said "NanoClaw acted" even when the broker's answer was
   `not_found` or an error. It now says so only for `done`. The audit page also has words for
   `interrupted` and `error`.
5. **`make lint`, `typecheck`, `test` and `install` masked `api/` failures.**
   - **Cause:** each target loops over `api broker` with a shell `for`, and a loop's exit status
     is its last iteration's. So an `api/` failure was hidden whenever `broker/` passed, in
     `make ci` and in GitHub's `check` job alike.
   - **Confirmed:** with two ruff errors in `api/`, `make lint` exited 0. With `|| exit 1` in
     each loop, it exits 2.
   - **Release 1:** that run's log shows no masked failure.
6. **Docs:**
   - architecture §2 (the console also holds the audit volume);
   - §3.7 (the cache result `none`, and `write: true`);
   - §3.9 (a read that ncl refuses, versus one that is `unavailable`);
   - §4.3 (the actions take an id);
   - §4.8 and §4.9 (the fixes above, and an unknown action name is not audited);
   - B45 (`bad_id` is a 404), and a new B52;
   - `CLAUDE.md` (the four writes now exist);
   - the InlineMessage, Panel and AuditList cards;
   - `make help` for `compose-smoke`.

## What is deliberately not done

- **A process kill between the broker acting and the audit line** (SIGKILL, OOM, or WUD's
  `docker stop` ending a 25 s call) still leaves no line in the file. The broker's `request` log
  keeps the verb and id, but not the email.
  - **Closing it fully:** write an intent line (`sent`) before the call, and refuse if that line
    cannot be written. That adds a result value and a second line to every action.
  - **Left to the lead:** that is a change to the log's shape, not a fix inside it.
- **A cooldown on `tasks-run`.** The busy guard stops only concurrent repeats, so a second click
  after the first answer queues a second run. A `timeout` or `network` answer also leaves Confirm
  armed. Changing either changes the actions' behaviour, so the decision is the lead's.
- **`GET /api/audit` creates an empty `audit.jsonl`** when it checks `writable`. This is harmless,
  and not changed.
- **`recent()` skips a line it cannot parse** and does not count it. Counting it would add a field
  to `/api/audit`, so it is left out of this PR.
