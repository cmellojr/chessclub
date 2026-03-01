# chessclub — User Guide

This guide covers installation, authentication, and all CLI commands with
real example outputs.

---

## Installation

```bash
git clone https://github.com/cmellojr/chessclub.git
cd chessclub
pip install -e .
```

Verify:

```
$ chessclub --help

 Usage: chessclub [OPTIONS] COMMAND [ARGS]...

╭─ Options ──────────────────────────────────────────────────╮
│ --help   Show this message and exit.                       │
╰────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────╮
│ auth   Manage Chess.com authentication.                    │
│ club   Club-related commands.                              │
╰────────────────────────────────────────────────────────────╯
```

---

## Authentication

Most commands require Chess.com credentials. There are two methods.

### Method 1 — Cookies (recommended)

**Prerequisite:** install the `chessclub Cookie Helper` Chrome extension by
loading it unpacked from `tools/chessclub-cookie-helper/`.

```
$ chessclub auth setup

Opening https://www.chess.com in the browser...
Log in and click the extension icon in the browser toolbar.

Paste ACCESS_TOKEN: ****
Paste PHPSESSID   : ****

✓ Credentials saved to ~/.config/chessclub/credentials.json
```

### Method 2 — OAuth 2.0 (when available)

```
$ chessclub auth login
```

Opens the browser, completes the PKCE flow, and saves tokens to
`~/.config/chessclub/oauth_token.json`. Tokens refresh automatically.

> **Note:** requires `CHESSCOM_CLIENT_ID` set in the environment. A Chess.com
> developer application approval is pending.

### Credential status

```
$ chessclub auth status

OAuth token  : not configured
Cookie auth  : ✓ active
  ACCESS_TOKEN : ****...abcd
  PHPSESSID    : ****...ef12
```

### Clear credentials

```
$ chessclub auth clear
Credentials removed.
```

---

## Club Commands

All club commands accept `--output json` or `--output csv` for integration
with other tools.

### `chessclub club stats <slug>`

Displays general club information: name (with country flag), member count,
creation date, events played, and description.

```
$ chessclub club stats clube-de-xadrez-de-jundiai

╭──────────────────────────────────────────────────────────────────────────────╮
│                    🇧🇷 Clube de Xadrez de Jundiaí                           │
╰──────────────────────────────────────────────────────────────────────────────╯
  752 Members  |  Created on 15/02/2022  |  141 Events

Welcome to Clube de Xadrez de Jundiaí! We are a traditional club located in
Jundiaí, SP. We host monthly tournaments, classes, and events for players of
all levels.
```

> **Note:** the event count requires authentication (counts internal
> tournaments). Without credentials, that field is omitted from the line.

**JSON output:**

```
$ chessclub club stats clube-de-xadrez-de-jundiai --output json

{
  "id": "clube-de-xadrez-de-jundiai",
  "provider_id": "352057",
  "name": "Clube de Xadrez de Jundiaí",
  "description": "<p>Welcome to...</p>",
  "country": "https://api.chess.com/pub/country/BR",
  "url": "https://www.chess.com/club/clube-de-xadrez-de-jundiai",
  "members_count": 752,
  "created_at": 1644940255,
  "location": "Rua São Jorge, 28 - 1o andar - Jundiaí - SP",
  "matches_count": 141
}
```

---

### `chessclub club members <slug>`

Lists all club members with their activity tier and join date.

```
$ chessclub club members clube-de-xadrez-de-jundiai

               Members — clube-de-xadrez-de-jundiai
 Username           Activity      Joined
 ─────────────────────────────────────────────────
 joaosilva          This week     2022-03-01
 mariaoliveira      This week     2022-05-14
 carlosmendes       This month    2023-01-20
 anapaula           Inactive      2022-02-20
 ...
 Total: 752 members
```

**With titles** (one API call per member — slow for large clubs):

```
$ chessclub club members clube-de-xadrez-de-jundiai --details

 Username           Title   Activity      Joined
 ──────────────────────────────────────────────────────
 joaosilva          FM      This week     2022-03-01
 mariaoliveira      —       This week     2022-05-14
 ...
```

**CSV output:**

```
$ chessclub club members clube-de-xadrez-de-jundiai --output csv

username,title,activity,joined_at
joaosilva,,weekly,1646092800
mariaoliveira,,weekly,1652486400
carlosmendes,,monthly,1674172800
```

---

### `chessclub club tournaments <slug>`

Lists all tournaments organised by the club, numbered oldest-first (`#1`) to
newest (`#N`). Requires authentication.

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai

                Tournaments — clube-de-xadrez-de-jundiai
  #    Name                                    Type    Date         Players
 ────────────────────────────────────────────────────────────────────────────
   1   1o Torneio XIII de Agosto               swiss   2022-03-05        12
   2   2o Torneio XIII de Agosto               swiss   2022-04-02        15
   3   1o Arena de Abertura                    arena   2022-04-16        24
  ...
 140   25o Torneio XIII de Agosto              swiss   2026-01-05        22
 141   26o Torneio XIII de Agosto              swiss   2026-02-01        24

 Total: 141 tournaments — use --games <#> to view games
```

**With standings for each tournament:**

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --details

  #    Name                         ...
 ─────────────────────────────────────
 ...

 ──────────── 26o Torneio XIII de Agosto ────────────
  #   Player           Score   Rating
  1   joaosilva        8.0     1850
  2   mariaoliveira    7.0     1740
  3   carlosmendes     6.5     1620
  ...
```

**JSON output:**

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --output json

[
  {
    "id": "6100001",
    "name": "1o Torneio XIII de Agosto",
    "tournament_type": "swiss",
    "status": "finished",
    "start_date": 1646438400,
    "end_date": 1646524800,
    "player_count": 12,
    "winner_username": "joaosilva",
    "winner_score": 9.0,
    "club_slug": "clube-de-xadrez-de-jundiai"
  },
  ...
]
```

---

### `chessclub club tournaments <slug> --games <ref>`

Shows all games from a specific tournament, ranked by Stockfish accuracy.
`<ref>` can be the list `#`, a partial name, or an exact ID.

**By list number:**

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --games 141

Tournament: 26o Torneio XIII de Agosto (ID: 6265185, 2026-02-01–2026-02-28)

          26o Torneio XIII de Agosto
 White            W%     Black            B%    Avg%   Result   Date         Link
 ─────────────────────────────────────────────────────────────────────────────────
 joaosilva        94.5   mariaoliveira    89.2   91.9   1-0      2026-02-03   view
 carlosmendes     87.1   anapaula         85.4   86.3   0-1      2026-02-03   view
 joaosilva        91.2   carlosmendes     78.6   84.9   1-0      2026-02-10   view
 ...

 Total: 47 games (32 with accuracy data, 24 participants)
```

> **Link:** in terminals that support hyperlinks (Windows Terminal, iTerm2),
> the `view` column is a clickable link that opens the game on Chess.com.

**By partial name:**

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --games "February"

Note: 3 tournaments matched. Using the most recent: 26o Torneio...
Tournament: ...
```

**By exact ID:**

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --games 6265185
```

**CSV output** (includes game URL):

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --games 141 --output csv

white,black,result,opening_eco,played_at,white_accuracy,black_accuracy,avg_accuracy,url
joaosilva,mariaoliveira,1-0,E20,1738540800,94.5,89.2,91.85,https://www.chess.com/game/live/...
...
```

---

### `chessclub club games <slug>`

Aggregates games from the last N club tournaments, ranked by accuracy.
Useful for identifying the highest-quality games in the club.

```
$ chessclub club games clube-de-xadrez-de-jundiai

 White            W%     Black            B%    Avg%   Result   Date
 ─────────────────────────────────────────────────────────────────────
 joaosilva        97.2   mariaoliveira    94.1   95.7   1-0      2026-02-10
 carlosmendes     93.8   joaosilva        92.5   93.2   0-1      2026-01-25
 ...

 Total: 231 games (189 with accuracy data)
```

**Changing the tournament window:**

```bash
# Last 10 tournaments (default: 5)
chessclub club games clube-de-xadrez-de-jundiai --last-n 10

# All tournaments (may be very slow)
chessclub club games clube-de-xadrez-de-jundiai --last-n 0
```

---

## Disk Cache

API responses are stored in `~/.cache/chessclub/` to avoid repeated network
calls. Current TTLs:

| Endpoint | TTL | Rationale |
|---|---|---|
| Game archives — past months | **30 days** | Historical archives are immutable |
| Game archives — current month | **1 hour** | Rounds happen within hours |
| Player profile | **24 hours** | Rating updated at most once per day |
| Club member list | **1 hour** | Members join or leave infrequently |
| Club info | **24 hours** | Name and description almost never change |
| Tournament leaderboard | **7 days** | Finished tournament results are immutable |
| Club tournament list | **30 minutes** | New tournaments appear at most weekly |

**Clear the cache:**

```bash
rm -rf ~/.cache/chessclub/
```

---

## Python Library Usage

`chessclub` can be used directly as a Python package, without the CLI.

### Minimal setup

```python
from chessclub.providers.chesscom.auth import ChessComCookieAuth
from chessclub.providers.chesscom.client import ChessComClient
from chessclub.services.club_service import ClubService

auth = ChessComCookieAuth()          # reads ~/.config/chessclub/credentials.json
client = ChessComClient("my-app/1.0", auth=auth)
service = ClubService(client)
```

### Examples

**Club info:**

```python
club = service.get_club("clube-de-xadrez-de-jundiai")
print(club.name)           # "Clube de Xadrez de Jundiaí"
print(club.members_count)  # 752
print(club.created_at)     # 1644940255 (Unix timestamp)
```

**Members:**

```python
members = service.get_club_members("clube-de-xadrez-de-jundiai")
for m in members:
    print(m.username, m.activity, m.joined_at)
```

**Tournaments:**

```python
tournaments = service.get_club_tournaments("clube-de-xadrez-de-jundiai")
# sorted by end_date ascending
for t in sorted(tournaments, key=lambda t: t.end_date or 0):
    print(f"#{t.id}  {t.name}  ({t.player_count} players)")
```

**Games from a tournament:**

```python
# Find by partial name
matches = service.find_tournaments_by_name_or_id(
    "clube-de-xadrez-de-jundiai", "February 2026"
)
tournament = matches[0]

games = service.get_tournament_games(tournament)
for g in games:
    print(f"{g.white} vs {g.black}  {g.result}  avg={g.avg_accuracy:.1f}%  {g.url}")
```

**Standings:**

```python
results = service.get_tournament_results(
    tournament.id, tournament_type=tournament.tournament_type
)
for r in results:
    print(f"#{r.position}  {r.player}  {r.score} pts")
```

**Without authentication** (public endpoints only):

```python
client = ChessComClient("my-app/1.0")   # no auth
club = service.get_club("clube-de-xadrez-de-jundiai")    # ✓ public
members = service.get_club_members("clube-de-xadrez-de-jundiai")  # ✓ public
tournaments = service.get_club_tournaments(...)           # ✗ requires auth
```

### Error handling

```python
from chessclub.core.exceptions import AuthenticationRequiredError, ProviderError

try:
    tournaments = service.get_club_tournaments("my-club")
except AuthenticationRequiredError:
    print("Configure credentials with: chessclub auth setup")
except ProviderError as e:
    print(f"Platform error: {e}")
```

---

## Output Formats

All listing commands accept `--output`:

| Flag | Description |
|---|---|
| (omitted) | Coloured Rich table in the terminal |
| `--output json` | Formatted JSON, suitable for `jq` and scripts |
| `--output csv` | CSV with header, suitable for Excel / pandas |

**Example with `jq`:**

```bash
# Names of the most recent tournaments
chessclub club tournaments clube-de-xadrez-de-jundiai --output json \
  | jq '[-3:][].name'

# Average accuracy of games in the last tournament
chessclub club tournaments clube-de-xadrez-de-jundiai --games 141 --output json \
  | jq '[.[].avg_accuracy | select(. != null)] | add/length'
```
