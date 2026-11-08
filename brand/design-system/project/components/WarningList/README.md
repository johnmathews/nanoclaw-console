The problems the API found (`warnings` on the overview, `items` on W9's Problems page), worst first, each with what to do next where the console can link it.

## Use

- A list between 1px `line` rules, no box. Each item: the severity as a StatusMark with its word (Error is failing, Warning is degraded, Note is unknown), then the title in `body` weight 600, the detail in `caption` `ink-secondary`, and a line with when it happened (voice.md times) and, for a task, an "Open the task" link. From 640px the severity sits in a 7rem column beside the text.
- Keep the API's order: severity, then newest first.
- Empty: "Nothing needs a look." in `ink-secondary`, so an empty list never looks like a failed read.
- The titles and details are the API's words, written to voice.md; the console does not rewrite them.

## States

- Link: hover (2px underline), focus (the 2px `focus` outline).

## You provide

- The items, the page's clock, and an id prefix (each item's id is `<prefix>-<kind>-<index>`).
