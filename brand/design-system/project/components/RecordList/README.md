Records of one kind between hairline rules: a title, a quiet line under it, then the record's facts. The console's lists of channels, MCP servers, mounts, destinations, people, approvals and unwired channels are all one.

## Use

- A `ul` between 1px `line` rules (no box), each record `space-4` above and below. The title in `body` weight 600 (an `h3` when the page's sections are `h2`), the quiet line in `caption` `ink-secondary` (a type, a platform id in `--font-mono`), then a FactList or one or two `caption` lines.
- **A policy value** reads as words, then NanoClaw's own value in `--font-mono` `ink-secondary`, so it can be matched against `ncl`: "Dropped without a reply `strict`". A value the console has no words for is shown as its own words ("Decline notify `decline_notify`"), never hidden.
- **A secret's name, never its value.** An MCP server lists the names of its headers and env variables and how many arguments it takes, then says their values are not shown. Its address is the host only.
- Long ids and paths break anywhere, so nothing scrolls sideways at 390px.
- Each record has a stable id (`group-channel-<wiring>`, `mcp-<name>`, `mount-<n>`, `role-<n>`, `approval-<id>`, `channel-<messaging group>`), so a problem can link to it and the page scrolls there.
- Empty: one `body` line in `ink-secondary` that says none ("No MCP servers."), or that the read failed ("Couldn’t read the approvals."). Never an empty list.

## States

- Links inside: hover (2px underline), focus (the 2px `focus` outline). A record named by the page's hash is scrolled to once the page's answer has drawn it.

## You provide

- The records, each record's id, and the words for the empty and the failed list.
