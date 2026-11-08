# 2026-11-08 — Release 1 PR wrap-up

The `/done` pass before the release-1 PR (W3–W6, W8, W9) went up. It ran on engineering-team run
`manual-20261108T121535Z`. Each unit has its own entry from earlier today; this one covers only
what the wrap-up found and changed.

## What the wrap-up checked

- **Local CI:** `make ci` was green before and after the fixes.
  - **Before:** api 375 passed, broker 517, Vitest 171, Playwright 55.
  - **After:** api 390 passed, broker 518, and the others unchanged.
- **Images:** `make compose-smoke` passed both times, and the broker image builds and starts
  (`--help`, uid `1000:1000`).
- **Workflows:** the seven pinned action SHAs match their tags (`gh api`, checked one by one).
- **Secrets:** none found by the scan. The fixtures hold fixture ids and planted
  `PLANTED-SECRET` values only. The LAN IPs in the docs are private addresses.
- **Docs audit:** a separate agent cross-checked the docs against the code. It found five minor
  gaps and no stale claims, and all five are fixed:
  - `errors.py` added to architecture §3.1;
  - the §6 layout gained `Makefile`, the workflows, `docs/` and `journal/`;
  - `build-app` and `build-broker` added to the make table;
  - Pinia marked as registered with no store yet;
  - the third page list (`e2e/a11y.spec.ts`) named in the secret-absence note.

## Review findings fixed

The review was a separate agent's read of the whole diff. It found nothing critical or high, and
it confirmed that the broker registry has no write verbs (D2, D4).

1. **The host-log message leaked what the sample masked** (medium, confirmed by running it).
   - An ERROR line's message kept a URL's userinfo and its webhook path, and also `Bearer`
     values. That text is shown on Problems and on the Overview.
   - **Fix:** the message now gets the sample's masking before the key=value pairs are removed
     (B39).
2. **The host-log patterns were quadratic** (medium, confirmed).
   - The old module took more than 0.5 s on a 256 KiB line and did not finish the next cases
     within 240 s. These patterns run inside the request, so a single long line stalls every
     route.
   - **Fix:** the line is cut to 4 KiB first; the URL pattern has the scheme lookbehind (as in
     the broker's B16); secret keys are found by a check on the key instead of inside the
     pattern.
   - **Tests:** a test per adversarial shape, each under 0.5 s. All of them took milliseconds
     when uncapped, up to 80k characters.
3. **A failed JWKS refresh refused everyone, and every request retried it** (low).
   - Fetches are now throttled and serialised.
   - A failed refresh keeps the last good keys for 24 h (B40).
   - **A bug in the first version of this fix:** the new concurrency test showed that requests
     arriving mid-fetch skipped the fetch and found no keys. A completed-fetch counter fixed it.
4. **Broker strings were only stripped of userinfo** (low).
   - Every string now gets `redact_document`, so `Bearer` values are masked too (B41).
   - This changes values only; the wire contract (§3) is unchanged.
5. **`parse_time` raised `OverflowError` on times near year 1 or year 9999 with an offset**
   (low, confirmed). That would have made a whole view 500. It now returns null (B24).

## What is deliberately not done

These are left for the lead or release 2:

- **No Content-Security-Policy header.** The review suggested
  `default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`.
  - Nothing tests CSP: e2e runs against `vite preview`, not the API that would send the header.
  - A wrong policy would blank the live page, and the deploy would be the first place to see it.
  - It needs its own change, with a test through the API.
- **The base images and npm are not pinned by digest:** `node:22-alpine`, `python:3.13-slim`
  and `npm@11`. This is a policy call because the console auto-deploys. It is left to the lead.
- **The per-group timezone** (suspected, not checked). Group configs carry `timezone`, and the
  cron words use the single `NANOCLAW_TIMEZONE` (B20). Whether NanoClaw's scheduler honours a
  group's own zone was not checked against the fork.
- **No `## Shipping` section in `CLAUDE.md`.** The PR route was taken on the lead's instruction.
  Adding the section is left for the lead to confirm.
