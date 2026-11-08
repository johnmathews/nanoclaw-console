The read-write flag: whether a mount or an allowlist root can be written, in words, with read-write standing out as a caution.

## Use

- **Read-write** is a caution InlineMessage (`caution-ink`, `triangle-alert`, `role="status"`) with words that say what it means: "Read-write: the agent can change these files" on a group's mounts, "Read-write allowed" on an allowlist root, or a group card's mount count ("2 mounts, 1 read-write").
- **Read-only** is plain `caption` text in `ink-secondary`: "Read-only". It is the safe default, so it stays quiet.
- The element that holds it (a mount row, a root row) carries `data-access="read-write"` or `"read-only"`, so tests and people can find every writable one.
- Never colour alone, never a pen: write access is not a health check, and a caution is the one tone that means "weigh this".
- A mount NanoClaw makes read-only regardless (the allowlist's `nonMainReadOnly`) is shown as the API reports it; the allowlist section says the rule in words.

## States

- Read-write; read-only. No interactive states.

## You provide

- Whether it can be written, and optionally the words for each state.
