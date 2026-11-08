## How the NanoClaw console writes

Plain, calm and brief, to one reader who runs the system. Facts first, then the next step. The console reports what NanoClaw is doing; it never guesses, cheers or alarms. When it cannot see something, it says so rather than showing nothing.

## Rules

- **The answer first:** "Claude is answering." before the counts that show it.
- **Times as people read them:** "two minutes ago", "today at 07:00", "every day at 07:00". The exact time and the cron expression sit beside them for whoever needs them.
- **Small numbers as words** in sentences ("Two tasks are paused."); figures in tables and totals.
- **Name what is not visible:** "Not visible to the console", with where to look instead. Never a blank cell that could mean "none".
- **Errors say what happened and what to do:** "Couldn't reach the broker, so this page shows nothing new. It retries every 30 seconds."
- **No exclamation marks, no hype**, no "awesome" or "amazing".
- **Sentence case everywhere**, including buttons and labels. No uppercase eyebrows.

## Examples

| Instead of | Write |
| --- | --- |
| ERROR: broker unavailable | Couldn't reach the broker. It retries every 30 seconds. |
| Status: PAUSED | Paused. Resuming runs it once straight away. |
| `0 7 * * *` | Every day at 07:00 (`0 7 * * *`) |
| Auth failure detected!! | Claude refused NanoClaw's token three times in the last hour. |
| null | Not visible to the console |
