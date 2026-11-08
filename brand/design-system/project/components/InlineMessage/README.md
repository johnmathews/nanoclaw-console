A one- or two-line message next to the thing it is about, in one of four tones, always an icon and words together.

## Use

- `caption` text (or `body` where it leads a section) with a 16px Lucide icon, `space-2` apart, no box and no fill.
- **Error** (`error-ink`, `circle-alert`, `role="alert"`): something the console itself hit. "Couldn’t read tasks/documentation-summary.md." PageStatus's list of failed reads is one. Never for a failing check, which is a StatusMark.
- **Caution** (`caution-ink`, `triangle-alert`, `role="status"`): a fact the reader should weigh before acting, always in words. The paused task that would run at once on resume: "Paused — will run once immediately if resumed" (F9), in the TaskList and at the top of the task's page with when it last ran. A truncated task file. A read-write mount (AccessMark), a stale approval ("Waiting 147 days, and it never expires.", F19), a denied channel, and a host log cut at its line limit.
- **Success** (`ink`, `check`): release 2's confirmation after an action ("Paused. It will not run until it is resumed."). Never `pen`, never celebrate.
- **Info** (`ink-secondary`, `info`): a neutral fact. "This task also runs a script. The console doesn’t show scripts."
- For how the whole page stands with the API, use PageStatus's Banner.

## States

- Appears and disappears without motion. The live role is on the message itself; it is rendered with its words in it, so it is read out as it appears.

## You provide

- `tone` (`error`, `caution`, `success`, `info`) and the words, written to voice.md: what happened, then what to do or what it means. No exclamation marks.
