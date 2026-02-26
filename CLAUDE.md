# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A modular Python library and CLI for consuming chess platform APIs (Chess.com today; Lichess, Lishogi, and Xiangqi.com planned). The goal is a multi-platform abstraction layer built around the Provider Pattern, where the core domain never depends on any specific platform.

## Development Setup

```bash
# Install in editable mode (required before running the CLI)
pip install -e .

# Run the CLI after installation
chessclub --help
```

No linting or automated test runner is currently configured.

## Architecture

The project uses a strict layered architecture. Each layer depends only on the layers below it. The dependency rule is enforced by convention — no exceptions.

```
src/
├── chessclub/               # Core library (importable as a package)
│   ├── core/                # Domain layer — no external dependencies
│   │   ├── interfaces.py    # ChessProvider ABC
│   │   ├── models.py        # Domain models (dataclasses)
│   │   └── exceptions.py    # ChessclubError, AuthenticationRequiredError, ProviderError
│   │
│   ├── auth/                # Authentication abstractions + credential storage
│   │   ├── interfaces.py    # AuthCredentials (dataclass) + AuthProvider ABC
│   │   └── credentials.py   # File storage utility (~/.config/chessclub/credentials.json)
│   │
│   ├── providers/           # Platform-specific implementations
│   │   └── chesscom/
│   │       ├── auth.py      # ChessComCookieAuth + ChessComOAuth (stub)
│   │       └── client.py    # ChessComClient implements ChessProvider
│   │
│   └── services/            # Business logic
│       └── club_service.py  # ClubService receives ChessProvider via DI
│
└── chessclub_cli/           # CLI — composition root only
    └── main.py              # Typer app; the only place that imports concrete classes
```

### Dependency rule (never violate)

```
core/           — imports nothing from this project
auth/           — imports only from core/
providers/      — imports from core/ and auth/
services/       — imports only from core/
chessclub_cli/  — imports from all layers (composition root)
```

## Authentication Architecture

Authentication is a **separate layer** from providers. Providers receive an `AuthProvider` instance and apply credentials to their HTTP sessions; they have no knowledge of how credentials are obtained, stored, or refreshed.

### Interfaces (`auth/interfaces.py`)

- `AuthCredentials` — generic dataclass carrying `headers: dict` and `cookies: dict`.
- `AuthProvider` — ABC with `get_credentials() -> AuthCredentials` and `is_authenticated() -> bool`.

### Chess.com implementations (`providers/chesscom/auth.py`)

- `ChessComCookieAuth` — resolves `ACCESS_TOKEN` + `PHPSESSID` cookies in order:
  1. Constructor arguments
  2. `CHESSCOM_ACCESS_TOKEN` / `CHESSCOM_PHPSESSID` environment variables
  3. `~/.config/chessclub/credentials.json` (mode 0o600)
- `ChessComOAuth` — **stub only** (raises `NotImplementedError`). Placeholder for the future OAuth 2.0 flow once Chess.com grants application access. See: https://www.chess.com/clubs/forum/view/guide-applying-for-oauth-access

### Adding a new auth strategy

Implement `AuthProvider` and return an `AuthCredentials` with the appropriate headers/cookies. No changes to `core/`, `services/`, or `ChessComClient` are needed.

## Provider Pattern

`ChessProvider` (in `core/interfaces.py`) is the single abstract interface all providers must implement. It returns domain model instances — never raw dicts.

```python
class ChessProvider(ABC):
    def get_club(self, slug: str) -> Club: ...
    def get_club_members(self, slug: str) -> list[Member]: ...
    def get_club_tournaments(self, slug: str) -> list[Tournament]: ...
    def get_player(self, username: str) -> dict: ...
```

`ClubService` depends only on `ChessProvider` — it never imports a concrete provider.

### Adding a new platform (e.g. Lichess)

1. Create `providers/lichess/auth.py` → implement `AuthProvider` for Lichess tokens.
2. Create `providers/lichess/client.py` → implement `ChessProvider`.
3. Wire in `chessclub_cli/main.py` (composition root) — no other files change.

## Domain Models

All models are dataclasses defined in `core/models.py`. Providers must map raw API responses to these models before returning them.

| Model | Key fields |
|---|---|
| `Club` | `id` (slug), `provider_id` (platform numeric ID), `name`, `description`, `country`, `url` |
| `Member` | `username`, `rating`, `title`, `joined_at` |
| `Tournament` | `id`, `name`, `tournament_type`, `status`, `start_date`, `end_date`, `player_count`, `winner_username`, `winner_score` |
| `TournamentResult` | `tournament_id`, `player`, `position`, `score` (future use) |

## API Strategy — Chess.com

- **Public endpoints** (`api.chess.com/pub`): No auth needed — club info, members, player profiles.
- **Internal web endpoints** (`www.chess.com/callback`): Requires session cookies — club tournaments (auto-paginated). The numeric `club_id` is resolved from the public API response before calling these endpoints.

## CLI Command Structure

```
chessclub
├── club
│   ├── stats <slug>         # Club name (public API, no auth)
│   ├── members <slug>       # Member list (public API, no auth)
│   └── tournaments <slug>   # Tournaments organised by the club (requires auth)
└── auth
    ├── setup                # Guide user through browser cookie extraction and save
    ├── status               # Show credential source and validate with Chess.com
    └── clear                # Remove stored credentials file
```

The CLI (`chessclub_cli/main.py`) is the **composition root**: the only module that instantiates concrete classes (`ChessComCookieAuth`, `ChessComClient`). Everything else depends on abstractions.

## Exceptions

Use domain exceptions from `core/exceptions.py` — never Python built-ins as a proxy.

| Exception | When to raise |
|---|---|
| `AuthenticationRequiredError` | Provider receives HTTP 401 from an authenticated endpoint |
| `ProviderError` | Provider encounters an unrecoverable platform-specific error |
| `ChessclubError` | Base class — catch this to handle any library error generically |

## Branch Model

```
main      ← stable; every commit here is a release candidate
develop   ← integration; all active development happens here
feature/* ← short-lived; one per feature or fix, branched off develop
hotfix/*  ← urgent fixes branched off main; merged back to main AND develop
```

### Rules

- **`main`**: never commit directly. Only receives merges from `develop` (releases)
  or `hotfix/*` (urgent fixes). Every merge to `main` must be tagged (`v0.1.0`, …).
- **`develop`**: the day-to-day working branch. Broken or in-progress commits are
  acceptable here. All feature branches are created from and merged back into this branch.
- **`feature/<description>`**: branch off `develop`, delete after merge.
  Examples: `feature/lichess-provider`, `feature/json-output`, `fix/auth-expiry`.
- **`hotfix/<description>`**: branch off `main` for production-critical fixes only.
  Must be merged back into both `main` and `develop`.

### Workflow

```
feature/lichess-provider ──┐
feature/json-output      ──┤  merge when ready
fix/auth-expiry          ──┘
                            ↓
                         develop  ← validate here
                            ↓  when stable
                          main    ← tag: v0.2.0
```

## Code Style

Follows the **Google Python Style Guide** throughout.

- Docstrings: Google-style format with `Args` / `Returns` / `Raises` sections on all public APIs.
- Types: built-in generics (`list[dict]`, `str | None`) — no `typing.List` / `typing.Optional`.
- Imports: absolute only, grouped stdlib → third-party → local, one import per line.
- Line length: 80 characters maximum.
- Exceptions: specific types only — no bare `except:` or broad `except Exception`.
- All packages have `__init__.py`.
