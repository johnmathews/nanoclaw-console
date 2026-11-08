Every scheduled task, answering "what runs, for whom, when, and how has it gone": a table on a wide screen, a card per task on a phone.

## Use

- **From 1024px, a table** on `canvas`: header row in `label`, rows split by 1px `line` rules, cells in `caption`, top-aligned. Columns: Task, Group, Schedule, Next run, Last run, Runs, Status. The task's name is the row header, a link (weight 600, `body`) to the task's page.
- **Below 1024px, a card per task** (`panel`, 1px `line`, `radius-lg`, `space-4` padding): the name as a link, the status, then a FactList of the same five facts. Only one of the two is ever displayed, so nothing scrolls sideways at 390px.
- **The name** is the task file without `.md` when the prompt names one, else the prompt's first 60 characters cut at a word with "…", else the id.
- **Schedule** in words with the cron below it in `--font-mono` `ink-secondary`; a one-off task says "Once".
- **Times** in Europe/Amsterdam with the zone named, the relative phrase below (table) or in brackets (card). No next run says "Not while paused" or "Not scheduled"; no last run says "Never".
- **Runs** in figures: "123 runs, 3 failed", "5 runs, none failed", "No runs yet".
- **Status** in words: Scheduled, Running now, Paused (`ink-secondary`), Done, Failed, Cancelled. A paused task that would run at once on resume (F9) is a caution InlineMessage with exactly "Paused — will run once immediately if resumed". The status is not a StatusMark: a task's state is not a health check.
- Release 2 (W15) adds pause, resume and run on the task's own page, not here.

## States

- Name link: hover (2px underline), focus (the 2px `focus` outline).
- Empty: the page's answer line says "No scheduled tasks." and no table is drawn; if the list could not be read it says so instead (never "none").

## You provide

- The tasks from `/api/tasks`, already sorted (next run first, paused last), and the page's clock.
