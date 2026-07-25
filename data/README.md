# `data/` — committed datasets that cannot be regenerated

Everything else this pipeline consumes lives in `cache/` and can be re-fetched
from GitHub. What is in this directory cannot be. It is committed because git
is the only store here that nothing evicts.

## `frozen_star_history.json`

Stargazer records for twelve `autoware_ai*` repositories, recovered from a
cache snapshot taken on **2025-12-04**.

### Why it exists

GitHub [restricted listing a repository's stargazers][restriction] to its
collaborators. For a repository the CI token cannot list, the scalar
`stargazerCount` still works, but the per-date, per-person breakdown behind it
is unreadable — forever, not just until the next run.

Separately, the GitHub Actions cache holding these repositories' records was
evicted. `actions/cache` drops entries after 7 days without a hit and under the
repository's 10 GB budget; it is not a durable store, whatever CLAUDE.md
instructs. The two failures compounded: the records were gone, and the API
could no longer produce them again. Sixteen repositories lost their history,
and *Total Unique Stars* fell from 13,760 to 13,321 — a cumulative count of
distinct people moving backwards.

Eleven of those sixteen were recoverable because an old local copy of the cache
still held their identities. This file is that copy, reduced to the two fields
the pipeline actually reads.

### Contents

```json
{
  "captured_at": "2025-12-04",
  "reference": "https://github.blog/changelog/...",
  "repositories": {
    "<repository>": [["<login>", "YYYY-MM-DD"], ...]
  }
}
```

Twelve repositories, 940 records. `cursor` and `name` from the original
GraphQL edges are dropped. Dropping `cursor` matters beyond saving space: a
cursor implies the listing can be resumed, and for these repositories it cannot
be resumed at all. Records keep their original chronological order so the file
mirrors the shape of the live cache it stands in for.

`autoware_ai_utilities` is included even though it is still listable today, as
insurance for the day it is not. While it stays listable the live cache wins
and this entry is never read.

### Rules

**Never regenerate this file.** There is no source to regenerate it from. The
GitHub API cannot return these records, and rebuilding it from anything else
would silently substitute worse data for irreplaceable data.

**Never delete or truncate it.** `scripts/frozen_star_history.py` raises rather
than degrading to "no frozen history" if the file is missing or malformed —
this data exists precisely because it was once lost without a signal.

**Appending is legitimate in exactly one case:** another repository becomes
unlistable *and* a copy of its records survives somewhere. Add it with its own
capture date; do not backdate it into this snapshot.

### How it was produced

From a local `cache.zip` holding a `cache/raw_stargazer_data/` snapshot: for
every `autoware_ai*_stargazers.json`, each edge was reduced to
`[node.login, starredAt[:10]]`, preserving file order, and asserted to have
both fields present (no edge did not). The capture date was established from
two independent signals that agree: the cache files' mtimes (2025-12-03
21:09–21:12 JST) and the newest `starredAt` anywhere in the snapshot
(2025-12-04T03:43:21Z).

The conversion script is not committed. Its input is not in this repository,
so a committed copy would be dead code from the first day.

[restriction]: https://github.blog/changelog/2026-06-30-upcoming-access-restrictions-to-public-api-endpoints-and-ui-views/
