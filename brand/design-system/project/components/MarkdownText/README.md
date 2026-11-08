A Markdown file an agent wrote (a task's instructions, "what it will do"), rendered to HTML, sanitised, and set in the system's type.

## Use

- The file is untrusted: agents write it inside their containers. It is rendered with `marked` and then sanitised with DOMPurify before it reaches `v-html` (`web/src/lib/markdown.ts`). Only text tags survive: headings, paragraphs, lists, emphasis, code, quotes, rules, tables and links. No images (they would load from wherever the file says), no forms, frames, styles or scripts. Links keep only `http`, `https` and `mailto` targets and carry `rel="noopener noreferrer"`; a link that loses its target stays plain text, not underlined.
- Headings move down two levels, so a file's `#` is an h3 under the page's "What it will do" (title-1) and never a second h1. h3 is 22/28 weight 600; deeper headings are body weight 600.
- Body text 18/26, `space-3` between blocks, code in `--font-mono` at 16px, a `pre` block on `tile` that scrolls inside itself.
- Shown in a box (`panel`, 1px `line`, `radius-lg`) at most 65 characters wide, with the file's path above it in `--font-mono` `ink-secondary`.

## States

- Truncated: a caution InlineMessage above it, "The file is longer than the console reads (256 KiB); this is its start."
- No file: the page says why in words instead (the prompt names none, it is missing, or it could not be read).

## You provide

- The file's text. Never pass anything to `v-html` that has not been through `renderMarkdown`.
