NanoClaw's own host log, errors and warnings over 24 hours, grouped by message so a repeating line is one row with a count.

## Use

- Under a one-line summary in `body`: "8 errors and 13 warnings in the last 24 hours, in four groups by message." With none: "No errors or warnings in the last 24 hours."
- The rows are laid out like the WarningList: between 1px `line` rules, the level as a StatusMark with its word (ERROR and FATAL are Error, failing; WARN is Warning, degraded), in a 7rem column from 640px.
- Each row: the message in `body` weight 600 (the API's grouping key, with its `key=value` pairs removed); a `caption` `ink-secondary` line with the count in figures ("3 times") and "First …, last … (relative)" in voice.md times; then the sample, the newest line as the API masked it, in `--font-mono` `caption` `ink-secondary`, wrapping anywhere so it never scrolls sideways.
- The sample is shown as the API gives it and never more: the API cuts URLs to the host, masks Bearer and secret-looking values and cuts the line at 500 characters (architecture §4.5).
- Truncated: a caution InlineMessage, "More lines matched than the console reads (2000); these groups are from the newest."
- Loki did not answer: an error InlineMessage, "Couldn’t read NanoClaw’s host logs from Loki, so they are not shown." (PageStatus names the read too.)

## States

- Normal; truncated; none in the window; not read.

## You provide

- `host_logs` from `/api/problems` and the page's clock.
