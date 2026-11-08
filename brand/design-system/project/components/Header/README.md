The bar at the top of every page: the product's name, which goes to the overview, and the page navigation.

## Use

- One per page, full width, a 1px `line` rule below it; content inside follows the page's width (`max-w-7xl`, `space-4` gutters on a phone, `space-8` from 640px).
- The name in Source Serif 4 at 22/28 weight 600, the links in `body` `ink`. Each link is at least 44px tall.
- The current page's link has `aria-current="page"` and a 2px underline at 6px offset; a page below a section (a task's page under Tasks) keeps its section's underline, without `aria-current`. Hover draws a 1px underline. No colour change, no filled pill.
- On a phone the links wrap under the name, in the same order, which is the tab order.
- A skip link ("Skip to the page") comes before it in the tab order and is shown only while it has focus.
- Five pages, in this order: Overview, Tasks, Groups, Permissions, Problems (`web/src/lib/nav.ts`). A task's page keeps Tasks underlined and a group's page Groups. The bar has no actions of its own. On a phone the five wrap onto two lines under the name.

## States

- Link: default, hover (1px underline), current (2px underline), focus (the solid 2px `focus` outline at 2px offset).

## You provide

- The list of pages (name, path, label) and which section the current route belongs to.
