The audit log's entries between hairline rules, newest first: what was asked of which task or group, what came of it, then who asked and when.

## Use

- A RecordList: a `ul` between 1px `line` rules, each entry `space-4` above and below, one column at every width (an entry is three short lines, so a table would only add sideways scroll on a phone).
- **First line**, `body`: the action in weight 600 ("Pause", "Resume", "Run now", "Restart"), then the target's id in `--font-mono`, linked to the task's or group's page (2px underline on hover). An id the console refused to write down (it did not match the id pattern) reads "(an id the console refused to write down)" in `ink-secondary`, never the string that was sent.
- **Second line**, what came of it. A plain result is `caption` `ink` with no icon ("Done", "Done; one run queued", "Done; two containers restarted"). Anything else is an InlineMessage in its tone, so a refusal never reads as done:
  - info: "Already in that state; nothing changed";
  - caution: "Not found; nothing changed", "No waiting run to change", "Refused: the same action was still running", "Interrupted before NanoClaw answered; a later entry says what came of it";
  - error: "Refused: it did not come from the console’s own address" (and the other refusal reasons), "No answer from NanoClaw (timeout)", "The console failed during the action (RuntimeError)".
- **Third line**, `caption` `ink-secondary`, wrapping: the signed-in email, the time as a TimeText with its relative phrase, and Cloudflare's ray id ("ray `8c1d…-AMS`") when the request had one.
- Every field is picked by name; an entry is never printed key by key, so a field the API did not shape cannot reach the page.
- Each entry has `id="audit-<n>"` and `data-result`; its result line `audit-<n>-result`, its last line `audit-<n>-who`.
- Empty: "Nothing recorded yet." in `body` `ink-secondary`.
- In the app: `web/src/components/AuditList.vue`, on the audit page (`/audit`).

## States

- Link: hover (2px underline) and focus (the 2px `focus` outline).

## You provide

- The entries as `/api/audit` shapes them and the page's "now", for the times.
