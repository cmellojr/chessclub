# AGENTS.md

This file provides comprehensive guidance to AI coding agents and developers working in this repository. It serves as the single consolidated source of truth for architectural boundaries, development environment setup, coding conventions, and repository workflow practices (updated: May 2026).

---

## Quick Reference

- **Install:** `pip install -e .` then run `chessclub --help` to verify the CLI.
- **Linter & Formatter:** **Ruff** (configured in `pyproject.toml`). Run `ruff check src/` and `ruff format src/`.
- **Testing:** **Pytest** is configured. Run `pytest` to execute tests under the `tests/` directory.
- **Code Style:** **Google Python Style Guide** (80-character maximum line length, Google-style docstrings, absolute imports only, built-in generics for type hinting).

---

## Architectural Blueprint

The project implements a strict, platform-agnostic domain layer powered by the **Provider Pattern**.

```
src/
├── chessclub/               # Core library
│   ├── core/                # Domain layer — pure Python, zero local dependencies
│   │   ├── interfaces.py    # ChessProvider ABC
│   │   ├── models.py        # Domain models (dataclasses)
│   │   └── exceptions.py    # Custom domain exceptions
│   │
│   ├── auth/                # Authentication abstractions + credential storage
│   │   ├── interfaces.py    # AuthCredentials + AuthProvider ABCs
│   │   └── credentials.py   # Config and credential persistence helpers
│   │
│   ├── providers/           # Platform-specific integrations
│   │   ├── chesscom/        # Chess.com cookie, OAuth, and cache implementations
│   │   └── lichess/         # Lichess token-based authentication and ND-JSON clients
│   │
│   └── services/            # Pure business/analytics logic
│       ├── club_service.py            # Main club data orchestrator
│       ├── leaderboard_service.py     # Annual & monthly point aggregations
│       ├── rating_history_service.py  # Historical evolution tracking
│       ├── matchup_service.py         # Head-to-head member analytics
│       ├── attendance_service.py      # Participation rates & streaks
│       └── records_service.py         # Club highlights and records
│
└── chessclub_cli/           # Composition Root
    └── main.py              # CLI entry point (Typer app); instantiates concrete objects
```

### Dependency Rules (NEVER VIOLATE)

To maintain a strict layered structure, ensure imports only flow downwards:

```
core/           ─► imports nothing from this project
auth/           ─► imports only from core/
providers/      ─► imports from core/ and auth/
services/       ─► imports only from core/
chessclub_cli/  ─► composition root; imports from all layers
```

---

## Key Conventions

### 1. Domain Models as Dataclasses
All domain models must be defined as dataclasses in `core/models.py`. Concrete providers (e.g. Chess.com, Lichess) must map raw HTTP/JSON payloads directly to these domain models before returning them.

### 2. Exceptions Strategy
Never use standard Python exceptions (like `ValueError`, `KeyError`, or `RuntimeError`) as proxies for domain errors. Define or use custom exception types inheriting from `ChessclubError` in `core/exceptions.py`:
- `AuthenticationRequiredError`: Raised when an authenticated endpoint fails with 401.
- `ProviderError`: Raised for platform-specific API communication or data format failures.

### 3. Composition Root Pattern
Instantiations of concrete classes (e.g., specific `AuthProvider` or `ChessProvider` clients) are restricted to `chessclub_cli/main.py`. The library modules must depend exclusively on abstractions (`AuthProvider` and `ChessProvider` ABCs) via Dependency Injection.

### 4. Code Style & Quality
- **Line Length:** Hard limit at **80 characters**.
- **Docstrings:** Required for all public modules, functions, classes, and methods. Use Google format with explicit `Args`, `Returns`, and `Raises` sections.
- **Type Hinting:** Mandatory throughout the codebase. Use built-in generic types (`list[str]`, `dict[str, Any]`, `str | None`) rather than legacy `typing` structures.
- **Imports:** Absolute imports only (e.g., `from chessclub.core.models import Club`). Group imports in standard order: Standard Library, Third-party Dependencies, Local Modules.

---

## Detailed Documentation Pointers

To avoid duplication and ensure updates are kept in a single location, refer to the dedicated markdown files in the `docs/` folder:

- [docs/usage.md](docs/usage.md)
  * **Contents:** Comprehensive installation guides, authentication setup workflows (OAuth 2.0 PKCE Loopback vs. Session Cookies), library integration examples for external Python applications, output formatting, and verbose execution flags.
- [docs/features.md](docs/features.md)
  * **Contents:** Complete CLI command blueprints, subcommands structures (`club`, `player`, `auth`, `cache`), output structures, and details on how background logic performs pagination, Swiss leaderboards fallbacks, and hyperlinked terminal outputs.
- [docs/cache.md](docs/cache.md)
  * **Contents:** SQLite-based disk cache architecture located at `~/.cache/chessclub/cache.db`. Explains the table schemas, WAL journal modes, cache key serialization formats, and the distinct TTL policies mapped to API volatility.
- [docs/roadmap.md](docs/roadmap.md)
  * **Contents:** The project's evolutionary track. Includes current phase status (analytics, multi-identity/player aliases, opening analyses, styling profiles, frontend projects) and Architecture Decision Records (ADRs).

---

## Branch Model

```
main      ◄─── [Stable] Merge-only releases (tagged e.g. v0.1.0); never commit directly
develop   ◄─── [Integration] Day-to-day work, active development, and verification
feature/* ◄─── Short-lived development branches created from and merged to develop
hotfix/*  ◄─── Urgent production hotfixes off main; merged to both main and develop
```

- Every merge to `main` must represent a stable release candidate and receive a git tag.
- Delete `feature/*` and `hotfix/*` branches immediately upon successful merge.
