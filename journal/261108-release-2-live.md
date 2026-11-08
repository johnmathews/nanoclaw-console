# Release 2 live, and the security model written down

**2026-11-08, evening (CET).**

- PR #2 merged as `2c64541`. CI and `docker.yml` passed on `main`. WUD on the agent LXC redeployed the
  console at 20:15 and sent the "NanoClaw console updated" push.
- proxmox-setup then created the audit volume (`make agent t=console`) and moved the broker to
  `sha-2c64541`. The volume came up 10001:10001 0700, because the release-2 image was already in
  place when Docker first mounted it. Created earlier, it would have been root-owned.
- **Live checks, with John's go-ahead:**
  - pause and resume `weekly-learn-sweep-6ab9`: the status flipped both ways and its next run did
    not move;
  - restart the idle `slack_docs` group: `{restarted: 0}`;
  - a cross-site POST from another origin: stopped by Cloudflare Access and never logged by the
    console;
  - signed-in requests that each broke one guard rule: 403, each audited with its reason;
  - a hostile id: 404, audited with the id left out.

  "Run now" was not tried, because it spends tokens.
- Added `docs/security.md`: the assets and threats, the six layers, what a compromise of each piece
  gives, the deployment tradeoff (console on `latest` via WUD, broker pinned), and the accepted risks.
  The eight follow-ups from the run are issues #3–#10.
