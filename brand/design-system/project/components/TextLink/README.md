A link in `ink` with a visible underline, for going somewhere rather than doing something.

## Use

- `ink` text, a 1px underline at 3px offset, in the size of the text around it (`body` or `caption`). Inside an `ink-secondary` caption the link stays `ink`, so it reads as the one thing to press.
- In the console: "All tasks" above a task's name, "Open the task" in a WarningList item, "See every scheduled task" under the counts, a task's name in the TaskList (weight 600), "Go to the overview" on the not-found page, and links inside a task file (MarkdownText).
- The Header's page links are the one exception: no underline until hover or the current page.
- The underline is the cue, not the colour: never remove it, never colour a link `pen` or `focus`.
- Write the destination as words ("All tasks"), never "click here" or a bare URL. Actions that change something (release 2's pause, resume, run, restart) are Buttons, never links.

## States

- Hover: the underline thickens to 2px. No colour change.
- Focus: a solid 2px `focus` outline at 2px offset around the words.
- There is no disabled link: if the destination is not available, show plain text.

## You provide

- The words and the router target. The words alone must say where the link goes.
