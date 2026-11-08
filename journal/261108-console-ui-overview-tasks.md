# 2026-11-08 — Console UI: overview and scheduled tasks

The web app went from a placeholder page to its first two screens: the overview (is Claude
working, is NanoClaw running, what needs a look) and the scheduled tasks with a page per task
(what it is for, what it will do, when it runs). This is unit W8 of the engineering-team run
`manual-20261108T121535Z` in proxmox-setup. It builds on the JSON contract in
[docs/architecture.md](../docs/architecture.md) §4.7; the web app itself is §5 there, and the
choices are B26–B31 in [docs/decisions.md](../docs/decisions.md).

## What was built

- **The shell**: a skip link, the Header card (product name and navigation from
  `web/src/lib/nav.ts`) and `vue-router` on real paths. W9 adds Groups, Permissions and Problems
  as three nav entries and three routes; nothing else in the shell changes.
- **Overview**: an answer line ("Claude is answering NanoClaw’s agents. NanoClaw is running."),
  the warnings ("Needs a look"), then four cards. Claude: the status as a dot and a word, its
  reasons, last success, last agent call, agent calls in 24 h, refused tokens over 1 h and 24 h,
  and the probe. NanoClaw: health, uptime, channels, message loop, queue, sessions, groups, last
  message, tasks, or a plain "NanoClaw is not answering." Weekly quota under the API's
  `quota.label`, word for word (D6). Counts, with "Couldn’t read" where a read failed.
- **Tasks**: an answer line ("Six tasks. Two are paused, and each would run once straight away if
  resumed. Next: …"), then a table from 1024 px or a card per task below it. The paused
  documentation summary reads "Paused — will run once immediately if resumed" (F9).
- **A task's page**: the overdue warning with when it last ran, the task file rendered from
  Markdown and sanitised ("What it will do"), the full prompt, the run stats and recent run log,
  and the details (group, schedule with cron and zone, session, occurrence).
- **Every page** refreshes every 30 s through the backend, keeps its last answer when a refresh
  fails, shows `generated_at`, and names each failed read in `sources` in words with its code.

## The design system

Built from the system, per the design-system skill. Seven new cards: StatusMark, Header,
FactList, TaskList, WarningList, PageStatus and MarkdownText. Panel, InlineMessage, Banner and
TextLink were rewritten in the console's words on their first use, as the system's README asks.
`checks.json` requires the new cards and gains the `control-border` pairs the unknown ring
relies on. The gate passes with `--complete`, and every card renders at 375 px with no overflow.

**One question is open for John.** `foundations.md` left the status mark's shape to the first
screen with a status. The mockup `brand/design-system/mockups/261108-status-mark/` shows A (a
10px dot, recommended) and B (a 12px square) in both themes with contrast measured. The app is
built with A. B26 records it as provisional, and nobody has picked yet. The mockup is not
published as an Artifact; the lead can publish it or show the renders.

## Choices worth remembering

- **Task files are untrusted.** Agents write them inside their containers, so `marked` output goes
  through DOMPurify on a tag allowlist before `v-html`. Images are dropped, because they would
  make the browser fetch wherever the file points, and links keep only `http`, `https` and
  `mailto`. The fixture plants a script, an image and a `javascript:` link, and the tests check
  that none reach the page.
- **Two traps in Markdown tests.** A raw HTML line opens an HTML block that swallows the next
  line, so a planted `![img](…)` or `[x](javascript:…)` on the following line ends up as inert
  text. The test then passes for the wrong reason. The fixture separates each planted line with a
  blank line, so the sanitiser really has to strip them.
- **Times are Amsterdam's**, whatever the browser's zone (B29), with relative phrases rounded:
  1 min 48 s is "two minutes ago", and 365 days is "a year", not "12 months".
- **A task's status is not a health check**, so it gets words, not a pen (B31). On a task's own
  page the header says only "Paused", because the full warning follows directly below it.
- **The stripped planted link** keeps its words with no target, so only `a[href]` is underlined
  in a task file. A link that goes nowhere must not look like one.

## Test first

- **Libraries and the refresh composable**: collection failed first (5 files, modules missing).
  With empty stubs, 33 of 34 failed on assertions; the one pass was "no failed reads gives no
  problems", which an empty stub satisfies.
- **Shell and pages**: collection failed (no router). With a stub router over the old placeholder,
  42 of 42 failed (`getActivePinia()` was called but there was no active Pinia, then missing
  elements).
- **Red after the first implementation**:
  - `expected 'today at 15:28 CET (a minute ago)' to be '… (two minutes ago)'`: relative times
    floored, so they now round.
  - `'cli Connectedslack Connected'` and `'26 May at 09:03 CESTfive months ago'`: no text space
    between a stacked time and its phrase. Fixed with an explicit space; the channel test reads
    each list item.
  - The task-file test caught the HTML-block trap above.
  - `'in 12 months'` for 365 days: units now switch at 95 % of the next one.
  - `'… resumed. after that one run …'`: a lowercase sentence start when there is no last run.
  - `'At 17:00 every day0 17 * * *'`: a missing space before the cron.
  - My own first test asserted "the Loki did not answer"; the copy and the test were both fixed to
    "Loki did not answer".
- **Mutations, to prove the suites can fail** (each reverted):
  - The overdue words changed to "Paused": four Playwright tests fail (the row, the card and the
    task page at both widths).
  - A status word coloured `pen-partial`: axe fails both light overview runs with
    `color-contrast … 1.76`.
  - The sanitiser allowed `img` and `script`: two unit tests fail. Any URI allowed: two fail.

Result: 99 Vitest tests at 98 % branch coverage (floor 95), and 26 Playwright tests. The
Playwright tests cover axe on every page in light and dark at 1440 and 390 px, the degraded
overview, a 403, the paused task's warning at both widths, the header, a 503 on a task page, and
the 30 s refresh.

## Next

- John picks the status mark (A or B); then B26 and the mockup README get his words, and B is a
  three-line change in `StatusMark.vue` and its card.
- W9 adds Groups, Permissions and Problems on this shell; WarningList and PageStatus are ready for
  the Problems page.
- `README.md` still says "Status: scaffold", and `docs/development.md`'s web stack does not list
  `vue-router`, `marked` and `dompurify` (outside this unit's footprint).
