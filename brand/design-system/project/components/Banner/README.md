A full-width bar under the page's answer line saying how the page stands with the console's API, in words.

## Use

- Inside PageStatus's polite live region; it appears only when there is something to say.
- Layout: a 20px Lucide icon, a lead sentence in weight 600, then one sentence in `body`. `radius-md`, padding `space-3` by `space-4`.
- **Neutral** (`tile` fill, 1px `line` border, `cloud-off`, `ink`): the API or the broker could not be reached. "Couldn’t reach the console’s API, so this page shows what it had at 15:30 CET. It retries every 30 seconds." Before any answer: "Couldn’t reach the console’s API. It retries every 30 seconds."
- **Error** (`panel` fill, 1px `error-ink` border, `circle-alert` and lead in `error-ink`, the sentence in `ink`): the API refused the browser (401, 403), which only a reload can fix.
- No button: every page retries by itself every 30 seconds, and a refusal needs a reload, not a retry.
- Not for a single failed read (PageStatus's error InlineMessage) or for NanoClaw's own state (the overview's cards).

## States

- Clears itself on the next good answer. Nothing animates.

## You provide

- `tone` (`neutral`, `error`), the lead and the sentence.
