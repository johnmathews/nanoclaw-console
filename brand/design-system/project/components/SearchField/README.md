The one search box: a field with a search icon, a placeholder that says what it searches, a clear button, and a live line that says how many things match.

## Use

- TextField's skin (44px, `panel` fill, 1px `control-border`, `radius-sm`, `body` text), with a 20px Lucide `search` icon in `ink-secondary` at the left and, once there is text, a 44px clear IconButton (`x`, "Clear search") at the right.
- Inside a `role="search"` landmark. The label "Search notes" is in the markup but visually hidden: the icon and the placeholder make the purpose plain, and this is the only field where the label may hide.
- Placeholder names what is searched: "Search notes". Plain search over chronological records is enough (the Apple Notes lesson): no filters, no suggestions, no ranking chips.
- The status line below, `caption` in `ink-secondary`, `aria-live="polite"`, says the count in words with the query, in one wording: "No notes mention “knee”.", "One note mentions “knee”.", "Three notes mention “shoulder”." It is the only count and the only live region for search: the SearchResult rows that follow show no count of their own.

## States

- Hover: border `ink`. Focus: a solid 2px `focus` outline at 2px offset, on the field and on the clear button separately.
- Clear: empties the field, hides the button, clears the status and returns focus to the field. Escape does the same.
- No results: the status line says so, plainly, and nothing else changes.
- No disabled or error state: a search cannot be wrong.

## You provide

- The query (`v-model`), the count of matches for the status line, and the noun searched ("notes"). The component writes the status sentence, with small numbers as words.
- `placeholder` and the hidden `label` (both default to "Search notes").
