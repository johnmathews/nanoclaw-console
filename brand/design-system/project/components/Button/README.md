The text button in three weights: primary for the one action a step exists for, secondary for the other choices beside it, and quiet for the least of them.

## Use

- **Primary:** `ink` fill, `on-ink` text (K8: one colour for "act"). One per form or panel: "Sign in", "Create account", "Set password", "Add to my account", "Save".
- **Secondary:** transparent, 1px `control-border`, `ink` text. Alternatives next to a primary, or a row of equals: "Not mine", "Export", "Import…", "Retry".
- **Quiet:** no border, `ink` text, a `tile` fill on hover. The least likely choice or a way out: "Later", "Cancel", "This week".
- Shape: `radius-md`, the `body` size at weight 600, padding `space-4` (md) or `space-3` (sm). **md** is 44px tall and the default; **sm** is 36px for dense rows on desktop only (the Banner's action), and those become md (44px) below 640px, so every target on a phone stays 44px. On the Settings page, in dialogs and for Edit plan's Add buttons a Button takes the page's control size instead, 60u (48px folded) with 19u type (K51, K54, K55).
- Never the `pen` colour, never a brand blue. An icon on its own belongs in an IconButton.
- Order, everywhere: the secondary or cancel choice first, the primary last, at the right end of the row (quiet, then secondary, then primary when all three appear). Reading order follows the same sequence.

## States

- Hover: the primary lightens toward `canvas` (a `color-mix` of `ink` and `canvas`); secondary and quiet take a `tile` fill. Colour changes take 120ms, and none under reduced motion.
- Focus: a solid 2px `focus` outline at 2px offset, from `:focus-visible` (`.is-focus` in the preview).
- Busy: full colours, `aria-busy="true"`, and the label says what is happening ("Signing in…", "Saving…", "Adding…", "Importing…"). Never fade a label someone needs to read.
- Disabled: 40% opacity, only when nothing can happen yet. Prefer a message that says what is missing.

## You provide

- The label: a verb phrase in sentence case, no exclamation mark. The app's "Add Exercise" and "Add Food" become "Add exercise" and "Add food".
- The busy label, when the action takes time.
- `variant` (`primary`, `secondary`, `quiet`), `size` (`md`, `sm`), `type` (`button` unless it submits a form) and the click handler.
