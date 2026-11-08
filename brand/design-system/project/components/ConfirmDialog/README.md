A small modal question before the console acts on NanoClaw: the thing and its state now, what will happen, the action's caution, then two buttons. The console never uses the browser's `alert` or `confirm`.

## Use

- **The panel:** `panel` fill, 1px `line` border, `radius-lg`, `shadow-overlay` (none in dark, where the border is the edge), on the `scrim` at 40% (the opacity on the layer, never on the colour). `space-6` padding (`space-4` below 640px), at most 32rem (512px) wide, 16px from each screen edge on a phone, centred, scrolling inside if the screen is short. It appears without slide, scale or bounce.
- **Title** in `title-2`: the question, naming the thing ("Pause inbox-check?", "Resume documentation-summary?", "Run documentation-summary now?", "Restart main-group?").
- **State, then effect** in `body`, two short paragraphs. The state starts "Now:" and says what NanoClaw reports at this moment ("Now: paused. Its next run was due 27 May at 09:03 CEST.", "Now: one of its six sessions is running."). The effect says what will happen and what stays ("It won’t run until it is resumed. Its schedule and run history stay as they are.").
- **The caution** (an InlineMessage, caution) when the action has one, worded as the plan asks:
  - resuming an overdue task: "Its run is overdue, so it runs once now, as soon as it is resumed." (F9);
  - running a task: "A run spends tokens; it does not change the schedule.";
  - restarting a group: "A restart interrupts a running turn: the agent stops mid-reply." (or, with nothing running, "…; none is running now, so nothing stops.").
- **The audit line** in `caption` `ink-secondary`: "The console records this in its audit log with your sign-in."
- **Buttons:** secondary "Cancel", then primary with the verb from the title ("Pause", "Resume", "Run now", "Restart"). Never "OK" or "Yes", no "Are you sure", no warning icon in the title, no capitals.
- **No red button.** An action that interrupts something still uses the `ink` primary; the caution line and the verb do the work. `error-ink` is only for an error.
- Ask before every action that changes NanoClaw, even a reversible one: a run spends tokens and a restart cuts a reply short, and both are one click from a page that refreshes itself.
- In the app: `web/src/components/ui/ConfirmDialog.vue`, opened by `web/src/components/ActionBar.vue`.

## States

| State | Look |
| --- | --- |
| Open | focus on Cancel |
| Busy (the POST is out) | the primary says what is happening ("Pausing…", "Queuing…") with `aria-busy="true"`; Escape and a second press do nothing |
| Failed | an InlineMessage (error) above the audit line, saying what happened and what to do ("The console can’t write its audit log, so it didn’t act. Nothing changed."); the dialog stays open |
| Answered | it closes, focus returns to the button that opened it, and the page shows the answer under its heading ("Paused. It won’t run until you resume it.", "It was already paused, so nothing changed.") and refreshes |

## Accessibility

- Built on Reka UI's AlertDialog: `role="alertdialog"`, `aria-modal="true"`, `aria-labelledby` on the title and `aria-describedby` on the state and effect, so a screen reader reads both on open. Neither the panel nor the title takes an `id` of its own: Reka's ids are what those attributes point at.
- Focus starts on Cancel, the safe choice, and is trapped: Tab and Shift+Tab stay on the two buttons. Escape cancels. On closing, focus returns to the control that asked; a page's toggle (Pause becoming Resume) is the same button, so focus stays on it.
- While it is open the page behind is inert and hidden from assistive technology.
- `on-ink` on `ink`, `control-border` on `panel` and `caution-ink` on `panel` are measured by the gate; axe runs with each dialog open, in both themes, at 1440px and 390px (`web/e2e/w15.spec.ts`).

## You provide

The title (a question with the thing's name), the state now, the effect, the caution when there is one, the verb and its busy form, and the confirm and cancel handlers. The error, when the answer keeps it open.
