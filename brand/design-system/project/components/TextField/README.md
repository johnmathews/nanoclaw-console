A single-line input with its label always visible above it, an optional hint below, and an error that says what happened and what to do.

## Use

- On the Settings page and in dialogs a TextField takes the page's `--set-*` size instead, 60u tall (48px folded), its type at 19u (K51, K55).
- Field: 44px tall, `panel` fill, 1px `control-border`, `radius-sm`, `body` text in `ink`, padding `space-3`. Numbers (sets, reps, weight) add `tabular-nums` and the right `inputmode`.
- Label: `label` style in `ink`, `space-1` above the field. Always visible; a placeholder never stands in for it. The label names the thing and its unit only ("Weight in kg"); fields are not marked optional or required. When an empty field means something, its placeholder says what, in `ink-secondary`: "Bodyweight" in an empty Weight in kg. A placeholder is never an example value ("e.g. 12"). A hint below says what the label can't: "At least 10 characters." under a new password.
- Hint: `caption` in `ink-secondary`, `space-1` below, tied with `aria-describedby` ("At least 10 characters.").
- Error: `caption` in `error-ink` with the 16px `circle-alert` icon and words, tied with `aria-describedby`, the field set to `aria-invalid="true"` and its border to `error-ink`. The message replaces the hint and is announced (`role="alert"`) when it appears after a submit. Use it only when the problem belongs to that one field: "The passwords don't match. Type the same password in both fields." on Repeat password.
- Form-level error: when the problem belongs to more than one field and nobody can say which, the message appears once, below the fields, as an InlineMessage (error), and every field it concerns is marked `aria-invalid="true"` with its border in `error-ink` and is described by that one message (`aria-describedby` pointing at it). Sign-in works this way, because the server doesn't say whether the email or the password was wrong: "Wrong email or password. Check them and try again." under both fields, never on one of them.
- Placeholder text, when used at all, says what an empty field means, in `ink-secondary` ("Bodyweight"); never an example value ("e.g. 12") or an instruction.

## States

- Hover: the border darkens to `ink`. Focus: a solid 2px `focus` outline at 2px offset. Colour changes take 120ms, none under reduced motion.
- Error: as above, until the value changes.
- Disabled: the whole field (label included) at 40% opacity, only when it truly cannot be edited.

## You provide

- `label` (required), `id`, `type`, `autocomplete`, `inputmode`, the value (`v-model`), and optionally `hint` and `error` strings. The component wires `for`, `aria-describedby` and `aria-invalid`. For a form-level error, leave `error` empty and pass `invalid` plus an `aria-describedby` naming the shared message; the field adds its own hint to that.
- Error copy that names the problem and the next step: "The passwords don't match. Type the same password in both fields." (one field), "Wrong email or password. Check them and try again." (form-level, under both fields).
