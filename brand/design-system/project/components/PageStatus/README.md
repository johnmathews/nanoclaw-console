Under every page's answer line: how fresh the page is, whether the last refresh reached the API, and which reads failed.

## Use

- One polite live region holding up to three parts, `space-3` apart:
  - **A Banner** when the last load failed. Neutral (`cloud-off`) when the API could not be reached: "Couldn’t reach the console’s API, so this page shows what it had at 15:30 CET. It retries every 30 seconds." (without the "so…" clause before the first answer). Error tone on 401 or 403: "The console refused this browser (HTTP 403). Your Cloudflare Access sign-in may have ended: reload the page to sign in again." A page may give its own words (a task's page on 503: "Couldn’t reach the broker, so this task can’t be shown.").
  - **The freshness line** in `caption` `ink-secondary`, from the answer's `generated_at`: "Updated just now, at 15:30 CET. Refreshes every 30 seconds."
  - **An error InlineMessage** naming every read in `sources` that failed: "Some reads failed, so parts of this page are empty.", then one line each, "Couldn’t read the quota: the broker took too long to answer." with the code in `--font-mono`. So an empty card is never mistaken for "none".
- Every page refreshes itself every 30 seconds through the backend, so there is no Retry button.

## States

- Fresh; partly read; refresh failed with the last answer kept; never loaded; refused.

## You provide

- `generated_at`, the time of the last attempt, the load error (an HTTP status, or none for a network failure), `sources`, and optionally the page's own failure words.
