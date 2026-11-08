Facts about one thing as a description list: a label in `ink-secondary`, its value in `ink`.

## Use

- A `dl` of label and value pairs, both `caption`. From 640px two columns (labels at least 9rem, `space-6` apart, `space-2` between rows); on a phone each label sits above its value, `space-3` between pairs.
- For the cards' details (Claude, NanoClaw, Counts), a task card on a phone, and a task's runs and details.
- A value is never blank: what the console could not read says "Couldn’t read", what does not exist says "None" or "Never", and what is unknown says "Not known" (voice.md).
- Figures stay figures (counts and totals); times follow voice.md ("today at 15:28 CET (two minutes ago)").
- An id or a cron expression inside a value uses `--font-mono`.

## States

- None. Values may hold a StatusMark, a time or a link.

## You provide

- Each pair's label and value, and a stable `id` on a value a page or test needs.
