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

- **Club, member, and tournament data** — query any Chess.com club from your terminal
- **Tournament games ranked by accuracy** — fetch all games from club tournaments and sort by Stockfish accuracy; filter by `--min-accuracy`
- **Swiss + Arena support** — works for both tournament formats; falls back to the club member list when Chess.com does not expose a leaderboard for Swiss events
- **Member activity tiers** — `This week`, `This month`, or `Inactive` labels with join date; optional `--details` for title
- **Multiple output formats** — `--output table` (default), `--output json`, `--output csv` on all commands
- **Disk cache** — responses cached in `~/.cache/chessclub/` with TTLs calibrated to data volatility; repeated commands run instantly
- **Decoupled authentication** — cookie-based session auth and OAuth 2.0 PKCE with loopback server
- **Typed domain models** — `Club`, `Member`, `Tournament`, `Game` as Python dataclasses, never raw dicts
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
chessclub club tournament-games clube-de-xadrez-de-jundiai "26o Torneio"
```

---

## CLI Reference

### `auth` commands

| Command | Description |
|---|---|
| `chessclub auth setup` | Cookie fallback: save `ACCESS_TOKEN` + `PHPSESSID` from DevTools |
| `chessclub auth login` | OAuth 2.0 PKCE browser flow — tokens auto-refresh |
| `chessclub auth status` | Show configured credentials and validate them |
| `chessclub auth clear` | Remove all saved credentials |

### `club` commands

All `club` commands accept `--output` / `-o`: `table` (default), `json`, or `csv`.

| Command | Auth | Description |
|---|---|---|
| `club stats <slug>` | No | Club name, description, country, URL |
| `club members <slug> [--details]` | No | Members with activity tier, join date; `--details` adds title |
| `club tournaments <slug> [--details]` | **Yes** | Tournament list; `--details` adds per-player standings |
| `club games <slug> [--last-n N] [--min-accuracy X]` | **Yes** | Tournament games ranked by Stockfish accuracy |
| `club tournament-games <slug> <name-or-id>` | **Yes** | Games from one tournament, by name or ID |

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
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Name              ┃ Type   ┃       Date ┃ Players ┃ Winner pts ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━┩
│ Club Championship │ swiss  │ 2025-01-10 │      24 │        8.5 │
│ Blitz Arena       │ arena  │ 2025-02-03 │      18 │       32.0 │
└───────────────────┴────────┴────────────┴─────────┴────────────┘
Total: 2 tournaments
```

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

### `club tournament-games`

Fetches all games from a single tournament, identified by name (partial,
case-insensitive) or exact numeric ID.

```bash
chessclub club tournament-games clube-de-xadrez-de-jundiai "26o Torneio"
chessclub club tournament-games clube-de-xadrez-de-jundiai 6265185
```

When multiple tournaments match the name, the most recent one is used.

---

## Disk Cache

`chessclub` stores API responses in `~/.cache/chessclub/` to avoid repeating
network calls. The second run of any command is nearly instant.

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
To force a refresh: `rm -rf ~/.cache/chessclub/`

See [docs/cache.md](docs/cache.md) for the full implementation notes.

---

## Authentication

Some Chess.com endpoints require authentication. `chessclub` handles credentials
as a **separate layer** from the provider — the provider never knows how
credentials are obtained or stored.

### Cookie fallback (`auth setup`) — recommended

```bash
chessclub auth setup
```

Guides you through extracting session cookies from your browser DevTools:

| Cookie | Where to find it | Expiry |
|---|---|---|
| `ACCESS_TOKEN` | DevTools → Application → Cookies → chess.com | ~24 hours |
| `PHPSESSID` | DevTools → Application → Cookies → chess.com | Session |

Re-run `auth setup` when commands return authentication errors.

### OAuth 2.0 PKCE (`auth login`)

Implements the Authorization Code + PKCE flow with a Loopback Local Server
(RFC 8252). Tokens auto-refresh — no manual re-authentication needed.

> **Note:** requires `CHESSCOM_CLIENT_ID` set in the environment. The OAuth
> implementation is complete; a Chess.com developer application approval is
> pending.

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
│  · DiskCache          ~/.cache/chessclub/       │
└───────────────────┬─────────────────────────────┘
                    │ imports abstractions from
       ┌────────────▼──────────┐  ┌──────────────┐
       │  auth/                │  │  services/   │
       │  · AuthProvider (ABC) │  │  ClubService │
       │  · AuthCredentials    │  │  (core only) │
       │  · credentials store  │  └──────┬───────┘
       └───────────────────────┘         │
                                         │ imports
                        ┌────────────────▼──────────────┐
                        │  core/  (zero project imports) │
                        │  · ChessProvider (ABC)         │
                        │  · Club, Member, Tournament,   │
                        │    TournamentResult, Game      │
                        │  · ChessclubError hierarchy    │
                        └────────────────────────────────┘
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
│   │   ├── models.py         # Club, Member, Tournament, TournamentResult, Game
│   │   └── exceptions.py     # ChessclubError, AuthenticationRequiredError
│   ├── auth/
│   │   ├── interfaces.py     # AuthProvider ABC + AuthCredentials
│   │   └── credentials.py    # credentials.json + oauth_token.json
│   ├── providers/
│   │   └── chesscom/
│   │       ├── auth.py       # ChessComCookieAuth + ChessComOAuth
│   │       ├── cache.py      # DiskCache + CachedResponse
│   │       └── client.py     # ChessComClient
│   └── services/
│       └── club_service.py   # ClubService
└── chessclub_cli/
    └── main.py               # Typer CLI (composition root)
docs/
├── features.md               # Full CLI reference
├── cache.md                  # Cache design and TTL policy
└── roadmap.md                # Development roadmap
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
- [x] `club members` — activity tier, join date, optional title
- [x] `club tournaments --details` — per-player standings
- [x] `club games` — tournament games ranked by Stockfish accuracy
- [x] `club tournament-games` — games from a specific tournament
- [x] Disk cache — TTL-based, `~/.cache/chessclub/`
- [ ] `club leaderboard <slug> --year` — annual points aggregation
- [ ] Player aliases — group multiple usernames under one identity
- [ ] Head-to-head matchup table

See [docs/roadmap.md](docs/roadmap.md) for the full plan.

---

## Contributing

Target all pull requests at `develop`, not `main`. See [CLAUDE.md](CLAUDE.md)
for architecture conventions, dependency rules, and code style.

---

## License

Released under the [MIT License](LICENSE). Copyright © 2026 Carlos Mello Jr.
