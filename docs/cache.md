# chessclub — Disk Cache

## Why a cache?

Several `chessclub` commands are slow by nature. Fetching games for a club
tournament involves one HTTP request per participant per calendar month
(e.g. a 15-player club with a monthly tournament = 15+ requests). Without a
cache, re-running the same command even seconds later repeats all those
requests.

The cache eliminates redundant network calls by storing successful API
responses to disk and returning them instantly on subsequent runs — within
their time-to-live.

---

## Storage

The cache lives in a single SQLite database file:

```
~/.cache/chessclub/cache.db
```

Schema:

```sql
CREATE TABLE cache (
    key        TEXT PRIMARY KEY,   -- full request URL (+ serialised params)
    expires_at REAL NOT NULL,      -- Unix timestamp of expiry
    body       TEXT NOT NULL       -- JSON-serialised response body
);
CREATE INDEX idx_expires ON cache (expires_at);
```

The cache key is the full request URL. If query parameters are present
(e.g. `?page=1`) they are serialised with `json.dumps(params, sort_keys=True)`
and appended, ensuring page-level granularity.

Only **HTTP 200** responses are stored. Errors (404, 429, 401) always bypass
the cache — they are never written and the next request always goes to the
network.

WAL journal mode is enabled for better concurrent read performance and atomic
writes.

---

## TTL policy

TTLs are calibrated to the expected rate of change for each data type in the
context of a weekly/monthly chess club.

| Data | URL pattern | TTL | Rationale |
|---|---|---|---|
| Past game archives | `/games/{year}/{month}` (month < current) | **30 days** | Historical archives are immutable — a game played in January will never change |
| Current month archives | `/games/{year}/{month}` (current month) | **1 hour** | A club tournament spans several hours; re-runs within the same session use the cache |
| Player profile | `/pub/player/{username}` | **24 hours** | Rating and title are updated at most once per day |
| Club member list | `/pub/club/{slug}/members` | **1 hour** | Members join or leave infrequently |
| Club info | `/pub/club/{slug}` | **24 hours** | Name and description almost never change |
| Tournament leaderboard | `*/leaderboard` | **7 days** | Finished tournament results are immutable |
| Club tournament list | `/clubs/live/past/{id}` | **30 minutes** | New tournaments appear at most weekly |

---

## Implementation

The cache is implemented in
[`src/chessclub/providers/chesscom/cache.py`](../src/chessclub/providers/chesscom/cache.py)
and consists of two classes:

### `SQLiteCache`

Handles reading and writing cache entries via `sqlite3` (Python stdlib).

- **`get(key)`** — returns the cached `body` dict if the entry exists and has
  not expired; otherwise deletes the stale row and returns `None`.
- **`set(key, body, ttl)`** — writes the entry with `expires_at = now + ttl`
  using `INSERT OR REPLACE`. Write failures (e.g. read-only filesystem) are
  silently ignored — the cache is always optional.
- **`clear()`** — deletes all entries; returns the count removed. Used by
  `chessclub cache clear`.
- **`purge_expired()`** — deletes only entries whose TTL has elapsed; returns
  the count removed. Used by `chessclub cache clear --expired`.
- **`stats()`** — returns `{total, active, expired, size_bytes}`. Used by
  `chessclub cache stats`.

### `CachedResponse`

A lightweight stub that mimics the `requests.Response` interface. Used to
return cached data to calling code without needing a real HTTP response object.
Always reports `status_code = 200`. Implements `json()` and `raise_for_status()`
(no-op).

---

## Integration in `ChessComClient`

`ChessComClient` integrates the cache transparently via two internal methods:

### `_cache_ttl(url) -> int | None`

A `@staticmethod` that maps a URL to its TTL. Rules are applied in order;
the first match wins. Returns `None` if the URL should not be cached (e.g.
OAuth token exchange endpoints).

The method uses regex matching to detect game archive URLs and compares the
`(year, month)` extracted from the path against the current UTC month to
decide between the 30-day and 1-hour TTLs.

### `_cached_get(url, **kwargs) -> Response | CachedResponse`

Wraps `session.get()` with cache lookup and write logic:

```
_cached_get(url)
    │
    ├─ _cache_ttl(url) is None?  ──► session.get(url)  [bypass]
    │
    ├─ cache.get(cache_key) hit?  ──► CachedResponse(body)  [fast path]
    │
    └─ session.get(url)
           │
           ├─ status == 200?  ──► cache.set(key, body, ttl)
           │
           └─ return response  [errors pass through uncached]
```

All `session.get()` calls in the client go through `_cached_get()`:
`get_club`, `get_club_members`, `get_player`, `get_club_tournaments`,
`_try_leaderboard`, and the game archive loop in `get_tournament_games`.

---

## Clearing the cache

### Via CLI (recommended)

```bash
# Remove all entries
chessclub cache clear

# Remove only expired entries (keep still-valid responses)
chessclub cache clear --expired

# Inspect the cache before clearing
chessclub cache stats
```

### Manually

```bash
# Delete the entire database
rm ~/.cache/chessclub/cache.db
```

---

## Cache misses and stale data

Entries expire lazily: the stale row is deleted on the **first read** after
expiry, and the next request goes to the network. There is no background
cleanup process.

If you suspect a command is returning stale data (e.g. after a new member
joined mid-session), run:

```bash
chessclub cache clear --expired
```

Or clear everything and re-run the command:

```bash
chessclub cache clear
```
