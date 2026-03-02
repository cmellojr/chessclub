# chessclub — Feature Reference

This document describes every command available in the `chessclub` CLI, how
each one works internally, and what to expect from the output.

---

## Authentication

Most club-data endpoints on Chess.com require a valid session. The `auth`
group manages credentials locally under `~/.config/chessclub/`.

### `chessclub auth setup`

Saves Chess.com session cookies (cookie-based auth).

**How it works**

1. Opens Chess.com in the browser so you can log in normally.
2. You install the `chessclub Cookie Helper` Chrome extension (load unpacked
   from `tools/chessclub-cookie-helper/`) and click its icon to copy the
   `ACCESS_TOKEN` and `PHPSESSID` values.
3. Paste both values when prompted.
4. Makes a test request against the public API to validate the cookies.
5. Writes `~/.config/chessclub/credentials.json` (mode `0o600`).

**Notes**

- `ACCESS_TOKEN` typically expires within 24 hours. Re-run `auth setup` when
  commands start returning authentication errors.
- Cookie-based auth is the fallback when OAuth is not configured.

---

### `chessclub auth login`

Authenticates via **OAuth 2.0 PKCE + Loopback** (RFC 8252). Requires a
Chess.com developer `client_id`.

**How it works**

1. Opens the Chess.com authorisation page in the browser.
2. Starts a loopback HTTP server on a random local port to capture the
   authorisation code.
3. Exchanges the code for access + refresh tokens (PKCE — no client secret).
4. Writes `~/.config/chessclub/oauth_token.json` (mode `0o600`).

Access tokens are automatically refreshed when they are within 60 seconds of
expiry. Set `CHESSCOM_CLIENT_ID` in the environment before running this command.

---

### `chessclub auth status`

Shows which credentials are configured and validates them against the live API.

**Output**

```
✓ Cookie session   ~/.config/chessclub/credentials.json
Validating with Chess.com...
✓ Active credentials are valid.
```

---

### `chessclub auth clear`

Removes all saved credentials (`credentials.json` and `oauth_token.json`).

---

## Club commands

### `chessclub club stats <slug>`

Displays general information about a club retrieved from the Chess.com public
API (`api.chess.com/pub/club/{slug}`). No authentication required.

```
chessclub club stats clube-de-xadrez-de-jundiai
```

**Fields:** club name (with country flag emoji), member count, creation date,
events played (requires auth — counts internal tournaments), and description.

The output is formatted as an 80-column panel:

```
╭──────────────────────────────────────────────────────────────────────────────╮
│                    🇧🇷 Clube de Xadrez de Jundiaí                           │
╰──────────────────────────────────────────────────────────────────────────────╯
  752 Members  |  Created on 15/02/2022  |  141 Events

Welcome to Clube de Xadrez de Jundiaí! ...
```

> The event count requires authentication. Without credentials it is omitted.

**Output formats:** `--output table` (default), `--output json`, `--output csv`.

---

### `chessclub club members <slug> [--details]`

Lists all members of a club with their activity tier and join date.

```
chessclub club members clube-de-xadrez-de-jundiai
chessclub club members clube-de-xadrez-de-jundiai --details
```

**How it works**

1. Calls `GET api.chess.com/pub/club/{slug}/members`, which returns members
   grouped in three tiers: `weekly` (active in the last 7 days), `monthly`
   (last 30 days), and `all_time` (longer).
2. Merges all groups into a single flat list.
3. With `--details`: fetches each member's player profile
   (`GET api.chess.com/pub/player/{username}`) to populate the `Title` column.
   This adds one API call per member and is slower for large clubs.

**Activity tiers**

| Tier | Label | Colour |
|---|---|---|
| `weekly` | This week | green |
| `monthly` | This month | yellow |
| `all_time` | Inactive | dim |

**Output formats:** `--output table` (default), `--output json`, `--output csv`.

---

### `chessclub club tournaments <slug> [--details] [--games <ref>]`

Lists all past tournaments organised by the club, numbered oldest-first
(`#1` = oldest, `#N` = newest). Authentication required.

```
chessclub club tournaments clube-de-xadrez-de-jundiai
chessclub club tournaments clube-de-xadrez-de-jundiai --details
chessclub club tournaments clube-de-xadrez-de-jundiai --games 141
chessclub club tournaments clube-de-xadrez-de-jundiai --games "Fevereiro"
chessclub club tournaments clube-de-xadrez-de-jundiai --games 6265185
```

**How it works — tournament list**

1. Resolves the numeric `club_id` via the public API.
2. Paginates through `GET www.chess.com/callback/clubs/live/past/{club_id}`
   until an empty page is returned.
3. The response contains two tournament types:
   - `live_tournament` → mapped to type `swiss`
   - `arena` → mapped to type `arena`
4. Results are sorted oldest-first and numbered `#1 … #N`.
5. With `--details`: fetches the leaderboard for each tournament and prints a
   per-tournament standings table below the main list.

**How it works — `--games <ref>`**

`<ref>` is resolved in order:

1. If purely numeric and within `1 … N`: selects the tournament at that
   position in the oldest-first list.
2. Otherwise: passed to `find_tournaments_by_name_or_id` (case-insensitive
   substring match or exact ID). When multiple tournaments match a name, the
   most recent one is used.

After resolution, the same game-fetching logic as described below runs, and
the games table is printed instead of the tournament list.

**Authentication required** for the internal `callback` endpoint.

**Output formats:** `--output table`, `--output json`, `--output csv`.

---

### `chessclub club games <slug> [--last-n N] [--min-accuracy X]`

Lists tournament games ranked by average Stockfish accuracy (best first).
Aggregates across the last N tournaments.

```
chessclub club games clube-de-xadrez-de-jundiai
chessclub club games clube-de-xadrez-de-jundiai --last-n 3
chessclub club games clube-de-xadrez-de-jundiai --min-accuracy 85
chessclub club games clube-de-xadrez-de-jundiai --last-n 0   # all tournaments
```

**How it works**

1. Fetches all club tournaments (see `club tournaments` above).
2. Sorts tournaments newest-first and slices to `--last-n` (default 5;
   `0` = all tournaments).
3. For each tournament, resolves participants from the leaderboard endpoint
   (falls back to club member list on 404) then fetches game archives.
4. Deduplicates games that appear in more than one tournament window using the
   game URL as the canonical key.
5. Sorts all collected games by average accuracy descending. Games without
   accuracy data (Chess.com Game Review not run) appear last.

`--min-accuracy` filters out games below the threshold and games without
accuracy data.

**Authentication required.**

**Output formats:** `--output table`, `--output json`, `--output csv`.

---

### How games are fetched (shared logic)

Used by both `club tournaments --games` and `club games`:

1. Resolves participants from the tournament leaderboard:
   - **Arena:** `GET www.chess.com/callback/live/tournament/{id}/leaderboard`
   - **Swiss:** `GET www.chess.com/callback/live-tournament/{id}/leaderboard`
   - Each URL is retried up to 3 times on HTTP 429 with exponential back-off
     (1 s → 2 s → 4 s).
2. **Leaderboard fallback (Swiss):** Chess.com does not expose a consistent
   leaderboard endpoint for Swiss club tournaments. When both URLs return 404
   and the tournament has `player_count > 0`, the provider falls back to the
   full club member list as the participant set. Since all tournament entrants
   must be club members, this approximation is accurate in practice.
3. For each participant, fetches their monthly game archive
   (`GET api.chess.com/pub/player/{username}/games/{year}/{month}`) for every
   calendar month that overlaps the tournament window.
4. Keeps only games where:
   - Both `white` and `black` are in the participant set.
   - `end_time` falls within `[start_date, effective_end]` where
     `effective_end = max(end_date, start_date) + 6 hours` (buffer for rounds
     that finish after the official end time).
5. Deduplicates by game URL and sorts by average accuracy descending.

**Link column:** in terminals that support hyperlinks (Windows Terminal,
iTerm2), the `view` column is a clickable link that opens the game on
Chess.com.

---

## Cache commands

### `chessclub cache stats`

Shows the number of cached entries, active/expired breakdown, database
location, and file size.

```
Entries : 87 total  (85 active, 2 expired)
Location: ~/.cache/chessclub/cache.db
Size    : 1243.8 KB
```

---

### `chessclub cache clear [--expired]`

Removes cached API responses.

- Without flags: removes all entries.
- `--expired`: removes only entries whose TTL has elapsed, keeping still-valid
  responses in place.

The cache rebuilds automatically on the next command run.

---

## Output formats

All `club` commands accept `--output` / `-o` with three values:

| Value | Description |
|---|---|
| `table` | Rich-formatted table (default). |
| `json` | Pretty-printed JSON array, written to stdout. Suitable for piping. |
| `csv` | CSV with header row, written to stdout. |

JSON and CSV outputs are machine-readable and bypass all Rich formatting.

---

## Active auth method selection

The CLI automatically picks the best available authentication method:

1. **OAuth 2.0** — when `CHESSCOM_CLIENT_ID` is set **and**
   `~/.config/chessclub/oauth_token.json` exists. Tokens auto-refresh.
2. **Cookie session** — otherwise (env vars `CHESSCOM_ACCESS_TOKEN` /
   `CHESSCOM_PHPSESSID`, or `~/.config/chessclub/credentials.json`).
