A multi-line input that follows TextField's label, hint and error rules, for text longer than a line.

## Use

- Same skin as TextField: `panel` fill, 1px `control-border`, `radius-sm`, `body` text in `ink`, padding `space-3`. At least 104px tall (four lines), resizable vertically only.
- Label in `label` style, always visible, `space-1` above. Hint and character count in `caption` `ink-secondary` below, the count in `tabular-nums`.
- For free text the person writes, such as a note on an exercise or a set. NoteEditor restyles it for notes: a `tile` fill, the `note` style (Source Serif 4 italic, 16/24) and a 120px minimum height. Elsewhere use it as is.
- Never pre-fill it with a prompt or a question, and no placeholder: notes belong to the person and are never asked for.
- Not for short values (a name, a number): use a TextField.

## States

- Hover: the border darkens to `ink`. Focus: a solid 2px `focus` outline at 2px offset.
- Count: shown once the text nears the limit, or always when the limit is tight; tied with `aria-describedby`.
- Error: `aria-invalid="true"`, the border in `error-ink`, and the `circle-alert` icon with words in `error-ink` below: what is wrong, then what to do ("This note is 2,140 characters. Shorten it to 2,000 or fewer to save it.").
- Disabled: 40% opacity on the whole field, only when it truly cannot be edited.

## You provide

- `label` (required), `id`, the value (`v-model`), and optionally `hint`, `maxLength` and `error`. The preview's 2,000-character limit is an example: the consumer sets the real one, and the hint and error name it.
