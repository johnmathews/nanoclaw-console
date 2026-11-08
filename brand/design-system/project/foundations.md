## Colour

Ten standard roles carry every screen: `canvas` (the page), `panel` (dialogs, cards), `tile` (quiet fills and hover), `line` (hairline rules, never a control border), `control-border` (inputs, outlined buttons), `ink` (text, icons and the primary button's fill), `on-ink`, `ink-secondary` (times, counts, hints), `error-ink` and `focus`.

Four project roles each mean exactly one thing:

| Role | Means | Never |
| --- | --- | --- |
| `pen` | OK: a healthy check's status mark | Links, buttons, decoration |
| `pen-partial` | Degraded: a check that works with a warning | Text (it is 1.5:1 in light), errors |
| `pen-missed` | Failing: a failing check's status mark | The console's own errors (`error-ink`) |
| `caution-ink` | A caution, always in words | Errors |

**The three pens** come from Tracker's green, yellow and red markers, with their values unchanged. `pen` reaches 4.5:1 as text on `canvas` and `panel`, and `pen` and `pen-missed` reach 3:1 as a mark on `canvas`, `panel` and `tile`, in both themes. `pen-partial` is 1.5–1.9:1 on the light grounds, so it is only ever a filled mark beside words, never text. The mark is a 10px dot (`radius-full`), with unknown as a hollow `control-border` ring (StatusMark card). That is option A of the mockup `mockups/261108-status-mark`, built while John's pick is open (decision B26).

## Type

Tracker's scale, kept whole: set large enough to read at arm's length. A dense table may use `caption` for its cells; nothing goes below it.

**Source Serif 4** for the page name and section titles, and italic for quoted text someone wrote (a task's prompt). **Source Sans 3** for everything else, numbers included, always with `font-variant-numeric: tabular-nums`. Both self-hosted.

**Monospace** (`--font-mono`, the system's own monospace face, nothing downloaded) only for text read character by character and copied: an id, a cron expression, a command. Never for numbers, labels or anything else.

| Style | Size | Use |
| --- | --- | --- |
| `display` | 44/48 serif 600 (36/40 below 640px) | The page's name, once per screen |
| `title-1` | 30/36 serif 600 | Section titles |
| `title-2` | 22/28 sans 600 | Dialog titles, card headings |
| `body-large` | 20/28 | The summary line under a section title |
| `body` | 18/26 | Running text, inputs, buttons, table cells |
| `caption` | 16/22 | Times, counts, hints in `ink-secondary` |
| `label` | 16/22 600 | Field labels, table headers. Sentence case. |
| `note` | 18/26 serif italic | Text someone wrote, quoted as written |

## Shape and depth

Hairline `line` rules, almost no shadow. Radius `radius-sm` 4px (fields, tiles, chips), `radius-md` 6px (buttons), `radius-lg` 10px (panels), `radius-full` (the Switch, status dots). `shadow-overlay` on dialogs in light; none in dark. Spacing on a 4px base, `space-1` to `space-16`.

## Focus and motion

Every interactive element shows a solid 2px `focus` outline at 2px offset, never clipped. Colour transitions last 120ms at most and stop under `prefers-reduced-motion`. A refresh never flashes or animates the page.

## Icons

Lucide outline icons at 1.5px stroke, 20px in buttons and 16px beside text, in `currentColor`. An icon-only button always has an accessible label and a 44px hit area.
