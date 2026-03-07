# AGENTS.md

This file provides guidance to AI coding agents working with this repository.
For the full reference (architecture, conventions, dependency rules, code style,
branch model), see [`CLAUDE.md`](CLAUDE.md) — this file summarises the essentials
and avoids duplicating that content.

## Quick Reference

- **Install:** `pip install -e .` then `chessclub --help`
- **No linter or test runner** is currently configured.
- **Google Python Style Guide** throughout (80-char lines, Google-style
  docstrings, built-in generics, absolute imports only).

## Dependency Rule (never violate)

```
core/           — imports nothing from this project
auth/           — imports only from core/
providers/      — imports from core/ and auth/
services/       — imports only from core/
chessclub_cli/  — imports from all layers (composition root)
```

## Key Conventions

- All domain models are **dataclasses** in `core/models.py` — providers must
  map raw API responses to these models before returning them.
- Use domain exceptions from `core/exceptions.py` — never Python built-ins.
- The CLI (`chessclub_cli/main.py`) is the **composition root**: the only place
  that imports concrete classes. Everything else depends on abstractions.
- Branch model: `develop` for daily work, `main` for releases (never commit
  directly), `feature/*` off develop, `hotfix/*` off main.
