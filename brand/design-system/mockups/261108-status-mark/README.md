# The status mark

**Question:** which shape marks a status (OK, degraded, failing) beside its words: a dot or a small
square. The pens, the words and the rest of the cards stay as they are; unknown is a hollow ring
in `control-border` either way.

**Status:** open. The app (W8) is built with the recommended option A until John picks.

**Link:** (not published yet: the lead publishes it, or shows the renders)

## Options

- **A.** A 10px dot (`radius-full`, which `foundations.md` already reserves for status dots), the
  word after it in `ink`. (Recommended: the foundations already name status dots, and a dot reads
  as a light, not as a checkbox or a tracker day.)
- **B.** A 12px square with 2px corners, the word after it: closer to tracker's filled day boxes.

Measured on the page, both themes: `pen` and `pen-missed` reach 3:1 on `panel`; `pen-partial` is
below 3:1 in light by design (the word carries it, B2); the unknown ring (`control-border`)
reaches 3:1.

## Decision

Pending. Built with A meanwhile, recorded as B26 in `docs/decisions.md` as provisional. When John
picks: the option, his words, the date.

## Rounds

- **1, 2026-11-08:** the first options (W8).
