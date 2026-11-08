Every agent group at a glance, answering "what is set up, and what may it reach": a Panel card per group, two across from 1024px.

## Use

- Each card is a Panel (`radius-lg`, 1px `line`, `shadow-overlay`, `space-4` padding on a phone, `space-6` from 640px). The group's name is a `title-2` link to its own page; its folder in `--font-mono` `ink-secondary` under it.
- Then a FactList of six facts, in this order: **Model** ("claude-opus-4-7, provider not set"), **Channels** (one line each: the channel's name and when it engages, "Terminal: when it is mentioned"; "None wired"), **MCP servers** (names only), **Mounts** (the AccessMark: a caution when any is read-write, "2 mounts, 1 read-write"), **Tasks** ("3 tasks, 2 paused (each would run once straight away if resumed)", F9), **Sessions** ("6, 1 running").
- A group whose config could not be read says "Couldn’t read" in Model, MCP servers and Mounts, never "None".
- A card is not a link as a whole: only the name is, so the facts stay selectable.
- The group's own page (W9) has the full detail: each channel's policies, MCP hosts, mounts and destinations, as RecordLists. Release 2 (W15) puts restart in that page's header, never on the card.

## States

- Name link: hover (2px underline), focus (the 2px `focus` outline). Cards align to the top; a short card does not stretch.

## You provide

- The groups from `/api/groups`, in the API's order.
