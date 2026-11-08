A status in words with a small mark before them: a 10px dot in the status's pen, or a hollow ring when the status is unknown.

## Use

- For a check's state and nothing else: Claude (OK, degraded, failing, unknown), NanoClaw's health, a channel's connection, the message loop, the probe, a problem's severity in the WarningList (Error is failing, Warning is degraded, Note is unknown), and a host log group's level in the LogGroupList (Error, Warning).
- The words carry the meaning, always (B2): the dot only repeats them. `pen-partial` is below 3:1 on the light grounds, so it is never text and never alone.
- The dot is `radius-full`, `size 10px`, filled with `pen`, `pen-partial` or `pen-missed`. Unknown is a 2px `control-border` ring, since it is not one of the three pens. `space-2` between the mark and the words; the words in `ink`, weight 600 (400 inside a FactList value).
- Not for a task's status: a task is scheduled, paused or done, which is not a health check (TaskList). Not for read-write access either (AccessMark).
- The shape is the recommended option A of the mockup `mockups/261108-status-mark` (a dot over a small square). John has not picked yet; decision B26 records it as provisional.

## States

- No interactive states. It sits in the text flow and wraps with it.

## You provide

- `status` (`ok`, `degraded`, `failing`, `unknown`) and, when the status's own name is not the right word, `label` ("Healthy", "Connected", "Not answering", "Warning").
- A stable `id` when a page or test needs to find it; it carries `data-status` for the machine-readable state.
