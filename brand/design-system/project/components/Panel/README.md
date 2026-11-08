The one raised surface: a `panel` box with a hairline border, the large radius and the overlay shadow, which the overview's cards, a task card and a task file are built on.

## Use

- `panel` fill, 1px `line` border, `radius-lg`, `shadow-overlay` (soft in light, none in dark, where the `panel` colour does the lifting).
- Padding `space-6`, `space-4` below 640px. Content inside is spaced `space-4`.
- In the console: the overview's four status cards (Claude, NanoClaw, Weekly quota, Counts), each a `section` titled by its `title-2` heading; a task's card on a phone (TaskList); the box around a task file (MarkdownText); a group's card (GroupList); and "Not visible to the console" (NotVisible). A release-2 dialog (W15) will sit on it too.
- Not for ordinary page content: the answer line, the warnings and a task's sections sit straight on `canvas`, separated by space and `line` rules. Never nest a Panel in a Panel, never give it a coloured edge or a tinted fill.
- Cards side by side in a grid align to the top; a short card does not stretch to its neighbour's height.

## States

- A Panel has no interactive states of its own. Its contents carry focus rings, which the Panel never clips: it does not set `overflow: hidden`.
- On a phone it takes the full width less the `space-4` gutters.

## You provide

- The content and its heading: a card is a `section` with `aria-labelledby` pointing at its `title-2`. A stable `id` for the card (`claude-card`, `quota-card`…).
