# chessclub

![Python](https://img.shields.io/badge/python-%3E%3D3.10-3776AB?logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/requests-%3E%3D2.31-brightgreen)
![Typer](https://img.shields.io/badge/typer-%3E%3D0.12-009688)
![Style: Google](https://img.shields.io/badge/style-Google%20Python%20Style%20Guide-4285F4)

**Multi-platform chess API library and CLI — unified abstraction for Chess.com, Lichess, and beyond.**

`chessclub` provides a single, consistent interface for querying chess platform data from the command line or from Python code. It is built around the [Provider Pattern](https://en.wikipedia.org/wiki/Provider_model): the core domain never depends on any specific platform, so adding support for a new provider is a matter of implementing one interface and one auth strategy — nothing else changes.

---

## Features

- **Query clubs, members, and tournaments** directly from your terminal
- **Multi-platform ready** — Chess.com today; Lichess, Lishogi, and Xiangqi.com on the roadmap
- **Decoupled authentication** — cookie-based auth now, OAuth 2.0 support once Chess.com grants access
- **Typed domain models** — `Club`, `Member`, `Tournament` as Python dataclasses, not raw dicts
- **Rich terminal output** — coloured, aligned tables via the [Rich](https://github.com/Textualize/rich) library
- **Google Python Style Guide** throughout — type annotations, Google-style docstrings, 80-char lines

---

## Quick Start

```bash
# Clone and install in editable mode
git clone https://github.com/cmellojr/chessclub.git
cd chessclub
pip install -e .

# Explore available commands
chessclub --help

# Query a club (no authentication required)
chessclub club stats chess-com-developer-community
chessclub club members chess-com-developer-community

# List tournaments (requires credentials — see Authentication below)
chessclub club tournaments chess-com-developer-community
```

---

## CLI Reference

### `club` commands

| Command | Description | Auth |
|---|---|---|
| `chessclub club stats <slug>` | Display the club's display name | No |
| `chessclub club members <slug>` | List all club members in a table | No |
| `chessclub club tournaments <slug>` | List tournaments organised by the club | **Yes** |

**Example output — `club members`:**

```
                Members — chess-com-developer-community
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Username                                        ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ erik                                            │
│ danya                                           │
│ ...                                             │
└─────────────────────────────────────────────────┘
```

**Example output — `club tournaments`:**

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

### `auth` commands

| Command | Description |
|---|---|
| `chessclub auth setup` | Interactive guide: open browser, extract cookies, save credentials |
| `chessclub auth status` | Show credential source and validate against Chess.com |
| `chessclub auth clear` | Remove the locally stored credentials file |

---

## Authentication

Some Chess.com endpoints (notably the tournament list) require valid session cookies.
`chessclub` handles credentials as a **separate layer** from the provider — the provider
itself never knows how credentials are obtained or stored.

### Setting up credentials

```bash
chessclub auth setup
```

This command opens [chess.com/login](https://www.chess.com/login) in your browser and
walks you through extracting the two required cookies from DevTools:

| Cookie | Where to find it | Expiry |
|---|---|---|
| `ACCESS_TOKEN` | DevTools → Application → Cookies → chess.com | ~24 hours |
| `PHPSESSID` | DevTools → Application → Cookies → chess.com | Session |

### Credential resolution order

When making an authenticated request, credentials are resolved in this order:

```
1. CHESSCOM_ACCESS_TOKEN + CHESSCOM_PHPSESSID  (environment variables)
2. ~/.config/chessclub/credentials.json        (saved by `auth setup`)
```

The credentials file is created with `0o600` permissions (owner read/write only).

> **Note:** `ACCESS_TOKEN` expires approximately every 24 hours. Re-run
> `chessclub auth setup` when it expires. OAuth 2.0 support is planned once
> Chess.com grants application access.

---

## Architecture

`chessclub` uses a strict layered architecture where each layer depends only on
the layers below it:

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
│  · ChessComOAuth      (stub — OAuth 2.0 future) │
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
                        │  · Club, Member, Tournament    │
                        │  · ChessclubError hierarchy    │
                        └────────────────────────────────┘
```

**Dependency rule:** `core/` imports nothing from this project. `services/` imports
only from `core/`. No layer imports from a layer above it.

### Adding a new platform (e.g. Lichess)

1. **`providers/lichess/auth.py`** — implement `AuthProvider` for Lichess API tokens.
2. **`providers/lichess/client.py`** — implement `ChessProvider` using the Lichess API.
3. **`chessclub_cli/main.py`** — wire the new provider in the composition root.

No changes to `core/`, `services/`, or any existing provider are needed.

---

## Project Structure

```
src/
├── chessclub/
│   ├── core/
│   │   ├── interfaces.py     # ChessProvider ABC
│   │   ├── models.py         # Club, Member, Tournament, TournamentResult
│   │   └── exceptions.py     # ChessclubError, AuthenticationRequiredError
│   ├── auth/
│   │   ├── interfaces.py     # AuthProvider ABC + AuthCredentials dataclass
│   │   └── credentials.py    # ~/.config/chessclub/credentials.json storage
│   ├── providers/
│   │   └── chesscom/
│   │       ├── auth.py       # ChessComCookieAuth + ChessComOAuth (stub)
│   │       └── client.py     # ChessComClient
│   └── services/
│       └── club_service.py   # ClubService
└── chessclub_cli/
    └── main.py               # Typer CLI (composition root)
```

---

## Roadmap

### Platforms
- [x] Chess.com
- [ ] Lichess
- [ ] Lishogi
- [ ] Xiangqi.com

### Authentication
- [x] Cookie-based auth (Chess.com)
- [ ] OAuth 2.0 (Chess.com — pending application approval)
- [ ] API token auth (Lichess)

### Features
- [ ] `--output json` / `--output csv` flag on all commands
- [ ] `club tournaments <slug> --details` — player standings per tournament
- [ ] `player stats <username>` — player profile and ratings

---

## Contributing

Contributions are welcome — bug reports, feature requests, and pull requests alike.

Before submitting a PR, please read [CLAUDE.md](CLAUDE.md) for the project's
architecture conventions, dependency rules, and code style guidelines.

```bash
# Install in development mode
pip install -e .

# Verify everything works
chessclub club stats chess-com-developer-community
```

---

## License

License to be defined. See repository settings.
