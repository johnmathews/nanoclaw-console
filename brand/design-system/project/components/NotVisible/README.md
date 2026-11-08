A Panel that names what the console cannot see, so a missing permission never reads as "none" (voice.md: name what is not visible).

## Use

- One Panel at the end of the permissions page, titled "Not visible to the console" in `title-2`. A `caption` line says why it matters and where to look instead ("Look in `ncl` or on the agent host.").
- Then each item from the API's `not_visible`: what, in `body` weight 600, and why, in `caption` `ink-secondary`. The API always lists per-group env values, OneCLI secret assignments and egress lockdown (F21).
- The words are the API's; the console does not add or drop items. When the API names a doc for an item, link it with a TextLink (the contract has no such field yet).
- It is a fact, not a warning: no caution tone, no StatusMark.

## States

- None.

## You provide

- The `not_visible` items.
