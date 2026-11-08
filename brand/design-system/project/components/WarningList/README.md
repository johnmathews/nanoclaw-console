The problems the API found (`warnings` on the overview, `items` on the Problems page), worst first, each with what to do next where the console can link it.

## Use

- A list between 1px `line` rules, no box. Each item: the severity as a StatusMark with its word (Error is failing, Warning is degraded, Note is unknown), then the title in `body` weight 600, the detail in `caption` `ink-secondary`, and a line with when it happened (voice.md times) and a link to what the item is about where its `ref` has a page: a task, "Open the task"; a group, "Open the group"; an approval, "See the approval" (its row on the permissions page); a channel, "See groups and channels" (anchored on the channel when the groups page draws it). A `source` item has none: PageStatus already names the failed read. From 640px the severity sits in a 7rem column beside the text.
- Keep the API's order: severity, then undated items, then newest first. The console never re-sorts.
- An item kind the console does not know is drawn the same way; the title and detail carry it.
- Empty: "Nothing needs a look." in `ink-secondary`, so an empty list never looks like a failed read.
- The titles and details are the API's words, written to voice.md; the console does not rewrite them.

## States

- Link: hover (2px underline), focus (the 2px `focus` outline).

## You provide

- The items, the page's clock, and an id prefix (each item's id is `<prefix>-<kind>-<index>`).
