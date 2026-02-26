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

- **Query clubs, members, and tournaments** directly from your terminal
- **Multi-platform ready** — Chess.com today; Lichess, Lishogi, and Xiangqi.com on the roadmap
- **Decoupled authentication** — cookie-based session auth and OAuth 2.0 PKCE with loopback server (awaiting Chess.com client_id)
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
| `chessclub auth login` | OAuth 2.0 PKCE browser flow — authenticate once, tokens auto-refresh |
| `chessclub auth setup` | Cookie fallback: extract session cookies from DevTools and save |
| `chessclub auth status` | Show OAuth token and/or cookie session status; validate against Chess.com |
| `chessclub auth clear` | Remove all locally stored credentials (OAuth token and cookies) |

---

## Authentication

Some Chess.com endpoints (notably the tournament list) require authentication.
`chessclub` handles credentials as a **separate layer** from the provider — the provider
never knows how credentials are obtained or stored.

### OAuth 2.0 PKCE (primary method)

```bash
chessclub auth login
```

Implements the Authorization Code + PKCE flow with a Loopback Local Server redirect URI
(RFC 8252), matching the pattern used by `gcloud`, `aws-cli`, and `gh`. The command:

1. Opens your browser to the Chess.com authorization page
2. Starts a temporary HTTP server on a random loopback port (`127.0.0.1:PORT`)
3. Captures the authorization code from the redirect automatically
4. Exchanges the code for an access token + refresh token
5. Saves tokens to `~/.config/chessclub/oauth_token.json` (`0o600` permissions)

Tokens refresh automatically — no manual re-authentication needed.

> **Note:** `auth login` requires a `CHESSCOM_CLIENT_ID` environment variable.
> The OAuth 2.0 implementation is complete; a developer application approval from
> Chess.com is pending. Once available, the `client_id` will be bundled in the
> package and no configuration will be needed by end users.

### Cookie fallback (`auth setup`)

```bash
chessclub auth setup
```

Until OAuth is fully activated, this command guides you through extracting session
cookies from your browser's DevTools:

| Cookie | Where to find it | Expiry |
|---|---|---|
| `ACCESS_TOKEN` | DevTools → Application → Cookies → chess.com | ~24 hours |
| `PHPSESSID` | DevTools → Application → Cookies → chess.com | Session |

### Credential resolution order

When making an authenticated request, the active method is selected in this order:

```
1. OAuth 2.0 token    (~/.config/chessclub/oauth_token.json)  ← preferred
2. Environment vars   CHESSCOM_ACCESS_TOKEN + CHESSCOM_PHPSESSID
3. Credentials file   ~/.config/chessclub/credentials.json (saved by auth setup)
```

All credential files are created with `0o600` permissions (owner read/write only).

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
│  · ChessComOAuth      OAuth 2.0 PKCE + Loopback Server      │
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
│   │   └── credentials.py    # credentials.json (cookies) + oauth_token.json (OAuth)
│   ├── providers/
│   │   └── chesscom/
│   │       ├── auth.py       # ChessComCookieAuth + ChessComOAuth (PKCE + loopback)
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
- [~] OAuth 2.0 PKCE + Loopback Server — implemented, awaiting Chess.com client_id
- [ ] API token auth (Lichess)

### Features
- [ ] `--output json` / `--output csv` flag on all commands
- [ ] `club tournaments <slug> --details` — player standings per tournament
- [ ] `player stats <username>` — player profile and ratings

---

## Contributing

Contributions are welcome — bug reports, feature requests, and pull requests alike.

### Branch model

| Branch | Purpose |
|---|---|
| `main` | Stable; tagged releases only |
| `develop` | Active development; target for all PRs |
| `feature/<name>` | New features and fixes, branched off `develop` |
| `hotfix/<name>` | Urgent production fixes, branched off `main` |

**Please target all pull requests at `develop`, not `main`.**

### Getting started

```bash
git clone https://github.com/cmellojr/chessclub.git
cd chessclub
git checkout develop

pip install -e .

# Verify everything works
chessclub club stats chess-com-developer-community
```

Before submitting a PR, please read [CLAUDE.md](CLAUDE.md) for the project's
architecture conventions, dependency rules, and code style guidelines.

---

## License

Released under the [MIT License](LICENSE). Copyright © 2026 Carlos Mello Jr.
