The text button in three weights: primary for the one action a step exists for, secondary for the choices beside it, and quiet for the least of them.

## Use

- **Primary:** `ink` fill, `on-ink` text: one colour for "act". One per dialog or step, and only where the action happens: the verb of a ConfirmDialog ("Pause", "Resume", "Run now", "Restart").
- **Secondary:** transparent, 1px `control-border`, `ink` text. A page's actions, which only open their ConfirmDialog (the task page's "Resume" or "Pause" and "Run now", the group page's "Restart"), and "Cancel" beside a primary.
- **Quiet:** no border, `ink` text, a `tile` fill on hover. The least likely choice. No console screen uses it yet.
- Shape: `radius-md`, the `body` size (18/26) at weight 600, `space-4` side padding, 44px tall at every width, so every target on a phone is 44px. The console has no small button: the dense rows that had one in Tracker are not here.
- Never the `pen` colours, never `error-ink`, never a brand blue: an action that stops or interrupts something is still `ink`, and the words do the work. An icon on its own belongs in an IconButton.
- Order, everywhere: the cancel choice first, the primary last, at the right end of the row. A page's actions sit at the right of its heading and wrap under it on a phone.
- In the app: `web/src/components/ui/AppButton.vue`.

## States

- Hover: the primary lightens toward `canvas` (a `color-mix` of `ink` and `canvas`, the `bg-ink-hover` utility); secondary and quiet take a `tile` fill. Colour changes take 120ms, and none under reduced motion.
- Focus: a solid 2px `focus` outline at 2px offset, from `:focus-visible` (`.is-focus` in the preview).
- Busy: full colours, `aria-busy="true"`, and the label says what is happening ("Pausing…", "Resuming…", "Queuing…", "Restarting…"). Never fade a label someone needs to read.
- Disabled: 40% opacity, only when nothing can happen yet. Prefer a message that says what is missing; the console's screens don't disable their actions, they explain a refusal instead.

## You provide

- The label: a verb phrase in sentence case, no exclamation mark ("Run now", not "Run Now!").
- The busy label, when the action takes time.
- `variant` (`primary`, `secondary`, `quiet`), `type` (`button` unless it submits a form) and the click handler.
