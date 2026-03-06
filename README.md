# chessclub

![Python](https://img.shields.io/badge/python-%3E%3D3.10-3776AB?logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/requests-%3E%3D2.31-brightgreen)
![Typer](https://img.shields.io/badge/typer-%3E%3D0.12-009688)
![License: MIT](https://img.shields.io/badge/license-MIT-yellow)
![Style: Google](https://img.shields.io/badge/style-Google%20Python%20Style%20Guide-4285F4)

**Multi-platform chess API library and CLI — unified abstraction for Chess.com, Lichess, and beyond.**

`chessclub` provides a single, consistent interface for querying chess platform data from the command line or from Python code. It is built around the [Provider Pattern](https://en.wikipedia.org/wiki/Provider_model): the core domain never depends on any specific platform, so adding support for a new provider is a matter of implementing one interface and one auth strategy — nothing else changes.

---

## Features

- **Club stats** — name (with country flag), member count, creation date, events played, and description in a clean 80-column layout
- **Member list with activity tiers** — general Chess.com activity: `This week`, `This month`, or `Inactive` labels with join date; optional `--details` for chess title
- **Tournament list + standings** — numbered oldest-first (`#1` = oldest, `#N` = newest); `--details` adds per-player standings
- **Tournament games ranked by accuracy** — `--games <ref>` on `tournaments` fetches all games sorted by Stockfish accuracy; `<ref>` is the list `#`, a partial name, or an exact ID
- **Clickable game links** — in terminals that support hyperlinks (Windows Terminal, iTerm2), the `view` column opens the game on Chess.com
- **Aggregate games view** — `club games` ranks all games across the last N tournaments by accuracy; filter with `--min-accuracy`
- **Club leaderboard** — `club leaderboard` aggregates tournament results by year or month and ranks players by total chess score
- **Rating history** — `player rating-history` tracks a player's rating evolution across club tournaments
- **Head-to-head matchups** — `club matchups` shows win/loss/draw records for every pair of players
- **Swiss + Arena support** — works for both tournament formats; falls back to the club member list when Chess.com does not expose a leaderboard for Swiss events
- **Multiple output formats** — `--output table` (default), `--output json`, `--output csv` on all commands
- **Disk cache** — SQLite-backed cache at `~/.cache/chessclub/cache.db` with TTLs calibrated to data volatility; repeated commands run instantly; managed via `chessclub cache stats/clear`
- **Decoupled authentication** — cookie-based session auth and OAuth 2.0 PKCE with loopback server
- **Typed domain models** — `Club`, `Member`, `Tournament`, `Game`, `PlayerStats`, `RatingSnapshot`, `Matchup` as Python dataclasses, never raw dicts
- **Rich terminal output** — coloured, aligned tables via the [Rich](https://github.com/Textualize/rich) library
- **Google Python Style Guide** throughout

---

## Quick Start

```bash
# Clone and install in editable mode
git clone https://github.com/cmellojr/chessclub.git
cd chessclub
pip install -e .

# Public commands — no authentication needed
chessclub club stats clube-de-xadrez-de-jundiai
chessclub club members clube-de-xadrez-de-jundiai

# Authenticated commands — run 'chessclub auth setup' first
chessclub club tournaments clube-de-xadrez-de-jundiai
chessclub club games clube-de-xadrez-de-jundiai --last-n 3

# View games from a specific tournament (by list #, name, or ID)
chessclub club tournaments clube-de-xadrez-de-jundiai --games 141
chessclub club tournaments clube-de-xadrez-de-jundiai --games "26o Torneio"

# Club analytics
chessclub club leaderboard clube-de-xadrez-de-jundiai --year 2025
chessclub club matchups clube-de-xadrez-de-jundiai --last-n 10
chessclub player rating-history joaosilva --club clube-de-xadrez-de-jundiai
```

---

## CLI Reference

### `auth` commands

| Command | Description |
|---|---|
| `chessclub auth setup` | Save Chess.com session cookies from the Cookie Helper extension |
| `chessclub auth login` | OAuth 2.0 PKCE browser flow — tokens auto-refresh |
| `chessclub auth status` | Show configured credentials and validate them |
| `chessclub auth clear` | Remove all saved credentials |

### `club` commands

All `club` commands accept `--output` / `-o`: `table` (default), `json`, or `csv`.

| Command | Auth | Description |
|---|---|---|
| `club stats <slug>` | No | Club name, member count, creation date, events, description |
| `club members <slug> [--details]` | No | Members with activity tier, join date; `--details` adds title |
| `club tournaments <slug> [--details] [--games <ref>]` | **Yes** | Tournament list (oldest-first); `--details` adds standings; `--games` shows games for one tournament |
| `club games <slug> [--last-n N] [--min-accuracy X]` | **Yes** | Tournament games ranked by Stockfish accuracy |
| `club leaderboard <slug> --year Y [--month M]` | **Yes** | Ranked player leaderboard for a year or month |
| `club matchups <slug> [--last-n N]` | **Yes** | Head-to-head win/loss/draw records between members |

### `player` commands

All `player` commands accept `--output` / `-o`: `table` (default), `json`, or `csv`.

| Command | Auth | Description |
|---|---|---|
| `player rating-history <username> --club <slug> [--last-n N]` | **Yes** | Rating evolution across club tournaments |

### `cache` commands

| Command | Description |
|---|---|
| `chessclub cache stats` | Show entry count, active/expired breakdown, and database size |
| `chessclub cache clear` | Remove all cached entries |
| `chessclub cache clear --expired` | Remove only entries whose TTL has elapsed |

---

### `club stats`

```bash
chessclub club stats clube-de-xadrez-de-jundiai
```

```
╭──────────────────────────────────────────────────────────────────────────────╮
│                    🇧🇷 Clube de Xadrez de Jundiaí                           │
╰──────────────────────────────────────────────────────────────────────────────╯
  752 Membros  |  Criado em 15/02/2022  |  141 Eventos

Bem-vindo(a) ao Clube de Xadrez de Jundiaí! Somos um clube tradicional
localizado em Jundiaí, SP. Promovemos torneios mensais, aulas e eventos para
jogadores de todos os níveis.
```

> **Note:** the event count requires authentication. Without credentials the
> line appears without that field.

---

### `club members`

```bash
chessclub club members clube-de-xadrez-de-jundiai
chessclub club members clube-de-xadrez-de-jundiai --details   # adds chess title (slower)
```

```
            Members — clube-de-xadrez-de-jundiai
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Username    ┃ Activity     ┃     Joined ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ alice       │ This week    │ 2023-04-01 │
│ bob         │ This month   │ 2022-11-15 │
│ carol       │ Inactive     │ 2021-06-30 │
└─────────────┴──────────────┴────────────┘
Total: 3 members
```

---

### `club tournaments`

```bash
chessclub club tournaments clube-de-xadrez-de-jundiai
chessclub club tournaments clube-de-xadrez-de-jundiai --details
```

```
                Tournaments — clube-de-xadrez-de-jundiai
┏━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┓
┃   # ┃ Name                       ┃ Type   ┃       Date ┃ Players ┃ Winner pts ┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━┩
│   1 │ 1o Torneio XIII de Agosto  │ swiss  │ 2022-03-05 │      12 │        9.0 │
│   2 │ 2o Torneio XIII de Agosto  │ swiss  │ 2022-04-02 │      15 │        8.5 │
│ ... │                            │        │            │         │            │
│ 141 │ 26o Torneio XIII de Agosto │ swiss  │ 2026-02-01 │      24 │        8.0 │
└─────┴────────────────────────────┴────────┴────────────┴─────────┴────────────┘
Total: 141 tournaments — use --games <#> to view games
```

---

### `club tournaments --games`

Fetch all games from a single tournament, ranked by Stockfish accuracy.
`<ref>` can be the `#` shown in the list, a partial name, or an exact ID.

```bash
# By list number
chessclub club tournaments clube-de-xadrez-de-jundiai --games 141

# By partial name (uses the most recent match when several match)
chessclub club tournaments clube-de-xadrez-de-jundiai --games "Fevereiro"

# By exact tournament ID
chessclub club tournaments clube-de-xadrez-de-jundiai --games 6265185
```

```
Tournament: 26o Torneio XIII de Agosto (ID: 6265185, 2026-02-01–2026-02-28)

          26o Torneio XIII de Agosto
 White            W%     Black            B%    Avg%   Result   Date         Link
 ─────────────────────────────────────────────────────────────────────────────────
 joaosilva        94.5   mariaoliveira    89.2   91.9   1-0      2026-02-03   view
 carlosmendes     87.1   anapaula         85.4   86.3   0-1      2026-02-03   view
 ...

 Total: 47 games (32 with accuracy data, 24 participants)
```

> In terminals that support hyperlinks (Windows Terminal, iTerm2) the `view`
> column is clickable and opens the game on Chess.com.

---

### `club games`

Fetches games from the *N* most recent tournaments and ranks them by average
Stockfish accuracy. Games without accuracy data (Game Review not run) appear last.

```bash
chessclub club games clube-de-xadrez-de-jundiai              # last 5 tournaments
chessclub club games clube-de-xadrez-de-jundiai --last-n 2
chessclub club games clube-de-xadrez-de-jundiai --min-accuracy 85
chessclub club games clube-de-xadrez-de-jundiai --last-n 0   # all tournaments
```

```
                    Tournament Games — clube-de-xadrez-de-jundiai
┏━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
┃ Tournament   ┃ White  ┃  W% ┃ Black        ┃   B%  ┃ Avg% ┃ Result ┃       Date ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
│ 6265185      │ alice  │ 94.3│ bob          │  91.2 │ 92.7 │ 1-0    │ 2026-02-25 │
│ 6265185      │ carol  │ 88.0│ alice        │  85.5 │ 86.7 │ 0-1    │ 2026-02-25 │
└──────────────┴────────┴─────┴──────────────┴───────┴──────┴────────┴────────────┘
Total: 2 games (2 with accuracy data)
```

---

## Disk Cache

`chessclub` stores API responses in a SQLite database at
`~/.cache/chessclub/cache.db`. The second run of any command is nearly instant.

| Data | TTL |
|---|---|
| Game archives — past months | 30 days (immutable) |
| Game archives — current month | 1 hour |
| Player profiles | 24 hours |
| Club member list | 1 hour |
| Club info | 24 hours |
| Tournament leaderboard | 7 days |
| Club tournament list | 30 minutes |

Only HTTP 200 responses are cached. Errors (404, 429) always go to the network.

```bash
chessclub cache stats            # entry count and database size
chessclub cache clear --expired  # remove only expired entries
chessclub cache clear            # remove everything
```

See [docs/cache.md](docs/cache.md) for the full implementation notes.

---

## Authentication

Some Chess.com endpoints require authentication. `chessclub` handles credentials
as a **separate layer** from the provider — the provider never knows how
credentials are obtained or stored.

Two complementary methods are available. Both are needed for full functionality:
OAuth 2.0 handles token-based authentication (auto-refresh), while cookies are
required for Chess.com internal endpoints used by tournament and game commands.

### Method 1 — OAuth 2.0 PKCE (`auth login`) — recommended

Implements the Authorization Code + PKCE flow with a Loopback Local Server
(RFC 8252). Tokens auto-refresh — no manual re-authentication needed.

#### Obtaining your `client_id`

Each user must request their own `client_id` from Chess.com. The ID is
personal and **must never be committed to the repository**.

1. Join the [Chess.com Developer Community](https://www.chess.com/club/chess-com-developer-community).
2. Fill out the [OAuth Application Form](https://forms.gle/RwGLuZkwDysCj2GV7)
   with the following details:
   - **Application name:** a name for your app (e.g. `chessclub-cli`)
   - **Redirect URI:** `http://localhost` (the CLI uses a loopback server on a
     random port — Chess.com accepts any `localhost` redirect)
   - **Description:** brief description of how you use the API
3. Chess.com will review and create an OAuth client for you. You will receive a
   **Client ID** (and optionally a Client Secret, which `chessclub` does not
   use — PKCE replaces it).
4. Set the environment variable before running the CLI:

```bash
# Linux / macOS
export CHESSCOM_CLIENT_ID="your-client-id-here"

# Windows (PowerShell)
$env:CHESSCOM_CLIENT_ID = "your-client-id-here"

# Windows (cmd)
set CHESSCOM_CLIENT_ID=your-client-id-here
```

> **Tip:** add the `export` / `$env:` line to your shell profile
> (`~/.bashrc`, `~/.zshrc`, PowerShell `$PROFILE`) so it persists across
> sessions.

5. Run the login flow:

```bash
chessclub auth login
```

The browser opens the Chess.com authorisation page. After you approve, a
loopback server captures the code and exchanges it for tokens. The access
token is saved to `~/.config/chessclub/oauth_token.json` and refreshes
automatically — you should not need to log in again.

#### Official documentation

- [Guide: Applying for OAuth access](https://www.chess.com/clubs/forum/view/guide-applying-for-oauth-access)
  (Chess.com Developer Community forum)
- [Getting started with Chess.com OAuth 2.0](https://chesscom.notion.site/Getting-started-with-Chess-com-OAuth-2-0-Server-5958e57c8c934a3aa7abda2d670969e8)
  (Notion — available after approval)

### Method 2 — Cookie session (`auth setup`)

Required for commands that use Chess.com internal endpoints (`club tournaments`,
`club games`, `club matchups`). These endpoints only accept session cookies.

```bash
chessclub auth setup
```

**Prerequisite:** install the `chessclub Cookie Helper` Chrome extension by
loading it unpacked from `tools/chessclub-cookie-helper/`. After logging in to
Chess.com, click the extension icon to copy your `ACCESS_TOKEN` and `PHPSESSID`,
then paste them when prompted.

| Cookie | Expiry |
|---|---|
| `ACCESS_TOKEN` | ~24 hours |
| `PHPSESSID` | Session |

Re-run `auth setup` when commands return authentication errors.

### Credential resolution order

```
1. OAuth 2.0 token    ~/.config/chessclub/oauth_token.json   ← preferred
2. Environment vars   CHESSCOM_ACCESS_TOKEN + CHESSCOM_PHPSESSID
3. Credentials file   ~/.config/chessclub/credentials.json
```

All files are created with `0o600` permissions.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  chessclub_cli  (composition root)              │
│  · only place concrete classes are instantiated │
└───────────────────┬─────────────────────────────┘
                    │ imports
┌───────────────────▼─────────────────────────────┐
│  providers/chesscom                             │
│  · ChessComClient     implements ChessProvider  │
│  · ChessComCookieAuth implements AuthProvider   │
│  · ChessComOAuth      OAuth 2.0 PKCE + Loopback │
│  · SQLiteCache        ~/.cache/chessclub/       │
└───────────────────┬─────────────────────────────┘
                    │ imports abstractions from
       ┌────────────▼──────────┐  ┌─────────────────────────┐
       │  auth/                │  │  services/              │
       │  · AuthProvider (ABC) │  │  · ClubService          │
       │  · AuthCredentials    │  │  · LeaderboardService   │
       │  · credentials store  │  │  · RatingHistoryService │
       └───────────────────────┘  │  · MatchupService       │
                                  │  (core only)            │
                                  └──────────┬──────────────┘
                                             │ imports
                        ┌────────────────────▼─────────────┐
                        │  core/  (zero project imports)    │
                        │  · ChessProvider (ABC)            │
                        │  · Club, Member, Tournament,      │
                        │    TournamentResult, Game,         │
                        │    PlayerStats, RatingSnapshot,    │
                        │    Matchup                         │
                        │  · ChessclubError hierarchy        │
                        └───────────────────────────────────┘
```

**Dependency rule:** `core/` imports nothing from this project. `services/`
imports only from `core/`. No layer imports from a layer above it.

### Adding a new platform (e.g. Lichess)

1. `providers/lichess/auth.py` — implement `AuthProvider`.
2. `providers/lichess/client.py` — implement `ChessProvider`.
3. `chessclub_cli/main.py` — wire in the composition root.

No other files change.

---

## Project Structure

```
src/
├── chessclub/
│   ├── core/
│   │   ├── interfaces.py     # ChessProvider ABC
│   │   ├── models.py         # Club, Member, Tournament, TournamentResult, Game,
│   │   │                     #   PlayerStats, RatingSnapshot, Matchup
│   │   └── exceptions.py     # ChessclubError, AuthenticationRequiredError
│   ├── auth/
│   │   ├── interfaces.py     # AuthProvider ABC + AuthCredentials
│   │   └── credentials.py    # credentials.json + oauth_token.json
│   ├── providers/
│   │   └── chesscom/
│   │       ├── auth.py       # ChessComCookieAuth + ChessComOAuth
│   │       ├── cache.py      # SQLiteCache + CachedResponse
│   │       └── client.py     # ChessComClient
│   └── services/
│       ├── club_service.py            # ClubService
│       ├── leaderboard_service.py     # LeaderboardService
│       ├── rating_history_service.py  # RatingHistoryService
│       └── matchup_service.py         # MatchupService
└── chessclub_cli/
    └── main.py               # Typer CLI (composition root)
docs/
├── features.md               # Detailed feature reference
├── usage.md                  # Full user guide with example outputs
├── cache.md                  # Cache design and TTL policy
└── roadmap.md                # Development roadmap
tools/
└── chessclub-cookie-helper/  # Chrome extension for extracting session cookies
tests/
├── test_models.py
└── test_cli.py
```

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Roadmap

### Platforms
- [x] Chess.com
- [ ] Lichess
- [ ] Lishogi

### Features
- [x] `--output json` / `--output csv` on all commands
- [x] `club stats` — enriched display: members, creation date, events, description with country flag
- [x] `club members` — activity tier, join date, optional title
- [x] `club tournaments --details` — per-player standings
- [x] `club tournaments --games <ref>` — games for a specific tournament by list #, name, or ID
- [x] `club games` — tournament games ranked by Stockfish accuracy
- [x] Disk cache — SQLite-backed, `~/.cache/chessclub/cache.db`; `chessclub cache stats/clear`
- [x] Clickable game hyperlinks in terminal output
- [x] `club leaderboard <slug> --year` — annual/monthly points aggregation
- [x] `player rating-history <username> --club <slug>` — rating evolution across tournaments
- [x] `club matchups <slug>` — head-to-head win/loss/draw table
- [ ] Player aliases — group multiple usernames under one identity

See [docs/roadmap.md](docs/roadmap.md) for the full plan.

---

## Contributing

Target all pull requests at `develop`, not `main`. See [CLAUDE.md](CLAUDE.md)
for architecture conventions, dependency rules, and code style.

---

## License

Released under the [MIT License](LICENSE). Copyright © 2026 Carlos Mello Jr.
