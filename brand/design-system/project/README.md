## About this document

This is the NanoClaw console design system. A design system is a product's design language (its colours, type, spacing and the way it writes), plus the components built from it and the rules for using them. This design system is not the app's code, but the code follows it closely. The app's styles are generated from its tokens, and the app's components are built from its cards.

This document shows each part of the console in light and dark. New screens are built from it, and the app is checked against it. It does not describe how the console works or what NanoClaw is; `docs/architecture.md` in the repo does that.

## Where it comes from

The console reuses the Tracker design system (`johnmathews/tracker`, `brand/design-system/`), chosen by John on 2026-11-08 (decision D9 in `docs/decisions.md`): the same colours, type, spacing, radii and focus ring, so his home-server apps look like one family. Only the product changed.

- **The tokens** are Tracker's values unchanged. Their usage notes are rewritten for the console. The three pens, which in Tracker mark a day great, partial or missed, here mark a status OK, degraded or failing (Foundations).
- **The cards** are the generic ones: Button, IconButton, TextLink, Panel, TextField, TextArea, SearchField, Switch, SegmentedControl, Dialog, ConfirmDialog, InlineMessage and Banner. Tracker's planner, notes, Ask, email and settings cards were left behind.
- **Copied as they were.** Each card's preview and README still carry Tracker's sample copy (exercises, weeks, the planner) and its decision numbers (K8, K55…), which resolve in Tracker's `docs/brand.md`. A card is rewritten for the console, in the console's words, the first time a console screen uses it, and before that screen is built.

## The feeling

- **Calm instrument.** A status page someone opens to check one thing and close again. Hairline rules, two typefaces, almost no shadow, nothing animated for its own sake.
- **Answer first.** Each screen leads with the one line that answers its question ("Is Claude working?", "What runs next?"), then the detail below it, dense and quiet.
- **Status in words.** A colour never carries a state alone: every OK, degraded or failing mark sits beside words that say the same.

## How to use this system

1. Read **Foundations** for colour, type, shape and motion, and **Voice** for how the console writes.
2. Build from the components. Each one's guidelines say when to use it, its states, and what the consumer provides. If something is missing, add it to the system first (preview and README), then use it.
3. Use tokens by name (`var(--ink)`, `var(--radius-md)`, the `.caption` class). Never paste a raw value.
4. Check every screen in light and dark, and at 375px wide.

## Never

- A secret on screen: a token, a header value, an env value. The console shows that a thing exists, never its value.
- A state shown by colour alone.
- The `pen` colours on anything but status marks.
- `pen-missed` standing in for `error-ink`: a failing check is a status; an error is something the console itself hit.
- Uppercase letter-spaced labels, gradients, glows, emoji, exclamation marks.
