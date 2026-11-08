The one raised surface: a `panel` box with a hairline border, the large radius and the overlay shadow, which Dialog, Popover and cards are built on.

## Use

- `panel` fill, 1px `line` border, `radius-lg`, `shadow-overlay` (soft in light, none in dark, where the `panel` colour does the lifting).
- Padding `space-6` for a card or a dialog; `space-4` for a popover body. Content inside is spaced with `space-2` to `space-4`.
- For something that sits above or apart from the page: the import prompt ("Data from before accounts"), the sign-in, sign-up, reset-your-password and email-confirmed cards, a dialog, the settings popover.
- Not for grouping ordinary page content: the grids sit straight on `canvas`, separated by `line` rules and space. Never nest a Panel in a Panel, never give it a coloured edge or a tinted fill.
- A title inside uses `title-2`; supporting text uses `body` or `caption` in `ink-secondary`; actions follow Button order: secondary or cancel first, primary last, at the right.

## States

- A Panel has no interactive states of its own. Its contents carry focus rings, which the Panel never clips: it does not set `overflow: hidden`.
- On a phone it takes the full width less the `space-4` gutters.

## You provide

- The content (the default slot), and a heading for it: give a card `aria-labelledby` pointing at its title, or an `aria-label` when there is no visible title.
- `padding` (`default` for `space-6`, `compact` for `space-4`). The element is up to the consumer: `section` for a card, the Dialog or Popover root for those.
