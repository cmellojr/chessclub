# Contributing to chessclub

Thank you for your interest in contributing! This document explains how to get started.

## Prerequisites

- Python 3.10+
- Git

## Development Setup

```bash
git clone https://github.com/cmellojr/chessclub.git
cd chessclub
pip install -e ".[dev]"
```

## Branch Model

| Branch | Purpose |
|---|---|
| `main` | Stable; never commit directly |
| `develop` | Day-to-day integration; all PRs target this branch |
| `feature/<name>` | New features or non-urgent fixes; branch off `develop` |
| `hotfix/<name>` | Urgent production fixes; branch off `main` |

**Always branch off `develop` for new work:**

```bash
git checkout develop
git pull origin develop
git checkout -b feature/my-feature
```

## Making Changes

1. Keep changes focused — one feature or fix per branch.
2. Follow the [dependency rule](CLAUDE.md#architecture): `core/` never imports from other layers; `services/` never imports from `providers/`.
3. Add domain models to `core/models.py`; never return raw dicts from services.
4. Use domain exceptions from `core/exceptions.py` — no bare `except:` or `except Exception`.

## Code Style

This project follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

- **Docstrings:** Google-style with `Args`, `Returns`, `Raises` on all public APIs.
- **Types:** built-in generics only — `list[str]`, `str | None`; no `typing.List` or `typing.Optional`.
- **Imports:** absolute only; grouped stdlib → third-party → local; one import per line.
- **Line length:** 80 characters maximum.

## Running Tests and Linting

```bash
pytest
ruff check src/          # lint (E/F/W/I/UP/B/SIM rules)
ruff format --check src/ # verify formatting
ruff format src/         # auto-format
```

Ruff configuration is in `pyproject.toml` under `[tool.ruff]`.

## Submitting a Pull Request

1. Push your branch and open a PR against `develop` (not `main`).
2. Describe *what* you changed and *why*.
3. If you added a new command or service, update the relevant docs in `docs/`.
4. If you added a new platform provider, update the architecture section in `CLAUDE.md`.

## Adding a New Platform Provider

The project is designed to be extended. The Lichess provider
(`src/chessclub/providers/lichess/`) is the reference implementation.

1. Create `src/chessclub/providers/<platform>/auth.py` — implement `AuthProvider`.
2. Create `src/chessclub/providers/<platform>/client.py` — implement `ChessProvider`.
3. Wire the new provider in `src/chessclub_cli/main.py` (composition root only).
4. No changes to `core/` or `services/` should be necessary.

See [CLAUDE.md](CLAUDE.md) for the full architecture guide.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you agree to abide by its terms.

## Questions

Open a [GitHub Issue](https://github.com/cmellojr/chessclub/issues) with the `question` label.
