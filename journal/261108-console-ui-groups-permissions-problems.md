# 2026-11-08 — Console UI: groups and channels, permissions, problems

The web app gained its last three release-1 views: groups and channels (question 2), permissions
(question 4) and problems, meaning errors and warnings (question 5). This is unit W9 of the
engineering-team run `manual-20261108T121535Z` in proxmox-setup. It builds on W8's shell and the
JSON contract in [docs/architecture.md](../docs/architecture.md) §4.7. The web app is §5 there
(§5.4 is new), and the choices are B32–B38 in [docs/decisions.md](../docs/decisions.md).

## What was built

- **Groups** (`/groups`): an answer line ("Three groups and five channels. Two channels are wired
  to no group. Two groups can write to files on the host."), then a card per group (model and
  provider, channels with when each engages, MCP server names, mounts with read-write flagged,
  tasks, sessions), then the channels wired to no group.
- **A group** (`/groups/:id`, new): settings, each wired channel's engage mode and pattern, sender
  scope, unknown-sender policy, other-message policy and session mode, then MCP servers (host or
  command, header and env *names*, "values are not shown"), mounts (read-write as a caution) and
  destinations. The header leaves room for release 2's restart.
- **Permissions** (`/permissions`): owners and admins, members, agent-to-agent policies (counted
  only, B34), who may message whom, the mount allowlist, approvals (the stale one: "Waiting 147
  days, and it never expires."), and the "Not visible to the console" panel.
- **Problems** (`/problems`): the items in the API's order, then NanoClaw's host log groups with
  count, first and last seen, and the masked sample.
- **Links:** a problem links by its `ref` to a task, a group, an approval's row or a channel's
  anchor, and the page scrolls there once it has drawn it. The overview's warnings use the same
  WarningList, so its stale approval and dropped messages link too.
- **Design system:** five new cards (RecordList, GroupList, AccessMark, LogGroupList,
  NotVisible) went into `brand/design-system/` before the screens; Header, WarningList,
  StatusMark, FactList, Panel, InlineMessage and TextLink gained the new uses. No new tokens. The
  gate passes with `--complete`, and every card renders at 375 px.
- Fixed two stale items W8 flagged: `README.md`'s status, and `docs/development.md`'s web stack
  (vue-router, marked, DOMPurify).

## Choices worth remembering

- **Words beside values.** Policies read as words with NanoClaw's value in monospace. The words
  come from NanoClaw's schema docs, but the live data carries `decline_notify`, which those docs
  do not list. So an unknown value shows as its own words rather than vanishing (B33).
- **Policies are a gap in the contract.** `/api/permissions` passes `policies` through unshaped
  (B22's one exception; the live table is empty). Showing a guessed field, or looping over keys,
  would show whatever redaction missed. The page counts them and points at `ncl policies list`.
  The API should shape them once a live row exists.
- **`not_visible` names no doc.** The plan wanted the panel to link the doc where one is named,
  but the contract's items are `{what, why}` only. The panel says where to look in words
  ("Look in `ncl` or on the agent host"); the NotVisible card says to link a doc once the API
  sends one.
- **No mockup** (B37): every new card arranges existing tokens and patterns. The read-write flag
  reuses the caution tone instead of inventing a marker.

## Test first

- **Libraries** (`groups`, `permissions`, `problems`): collection failed first (three files,
  modules missing). With empty stubs, 22 of 22 failed on assertions.
- **Pages, shell and secrets:** 42 of 48 failed before the pages existed. The 6 that passed were
  the fixture self-check, two shell tests the change does not touch, and the overview's secret
  test, because the overview fixture then carried no planted token. That made the test vacuous,
  so a token was planted in an overview warning too. Each per-page secret test also asserts that
  the page is not "Page not found", so a missing route can no longer pass it.
- **Red after the first implementation:**
  - `'John (DM): every messageTerminal: …'` and `'mainag-…'`: no text space between adjacent
    blocks, the trap W8 also hit. The ids line now has an explicit space, and the tests read
    each list item.
  - `'(32 minutes ago)'`: my test said "half an hour"; 13:58 to 14:30 is 32 minutes.
  - `dd:last-of-type` matched the first value, because each FactItem wraps its pair. The value
    now has an id.
- **Branch coverage** fell to 89.5 % (floor 95). A sparse-answer spec (every nullable field null,
  empty lists beside failed reads, singulars) took it to 97.2 % and checks each fallback's words.
- **Mutations**, each reverted:
  - Secret-absence: a hidden `<pre>` dumping each MCP server object turns the Vitest and
    Playwright tests red (`/groups/<main> shows a planted secret`). A key-by-key list of policy
    rows turns `/permissions` red, and so does an approval's JSON in a `title` attribute.
  - The read-write flag forced off: one Vitest and two Playwright tests fail.
  - `useHashTarget` removed: one Vitest test fails ("scrolls to the approval"), and so does the
    Playwright link test (`toBeInViewport`).

Result: 171 Vitest tests at 97.2 % branch coverage, and 55 Playwright tests. They run axe on all
seven pages in light and dark at 1440 and 390 px, axe on every problem kind, what each page shows
at both widths, the links, and the secret sweep over every page.

## Next

- The API should shape `policies` (and could add a doc link to `not_visible` items). Both are
  `api/` changes, outside this unit.
- B26's status-mark pick is still open; the new pages use the same mark.
