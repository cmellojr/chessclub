# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.2.0] — 2026-03-12

### Added
- **Lichess provider** — full `ChessProvider` implementation for Lichess API
  - `LichessTokenAuth` — token-based authentication (most endpoints are public)
  - `LichessClient` — supports teams, Swiss + Arena tournaments, ND-JSON streaming
  - `--provider` / `-p` global flag to select platform: `chesscom` (default) or `lichess`
- `club attendance` command — ranks players by tournament participation %, current streak, and all-time best streak
- `club records` command — highlights club records across all tournaments (highest score, most wins, biggest field, highest accuracy)
- `--year` is now optional on `club leaderboard`: omitting it returns an all-time ranking across all available tournaments
- `--verbose` / `-v` global flag — shows execution time and cache hit/miss stats after each command
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, and `CHANGELOG.md` added to the repository

### Changed
- Removed `club history` command (redundant with `club tournaments`, which is more complete)
- Timing and cache stats footer is now hidden by default; shown only with `--verbose`
- Configured `ruff` linter/formatter (E/F/W/I/UP/B/SIM rules) and applied first pass across codebase

### Fixed
- Auth layer now always sends session cookies alongside the OAuth Bearer header, ensuring internal Chess.com endpoints receive both credentials
- 404 responses are now cached to avoid redundant retries for missing resources

---

## [0.1.0] — 2026-03-05

First public release.

### Added

**CLI commands**
- `club stats <slug>` — club info, member count, activity indicators (public API; no auth required)
- `club members <slug>` — member list with activity tier; `--details` adds rating and join date
- `club tournaments <slug>` — full tournament history, oldest-first; `--details` shows per-tournament standings; `--games <ref>` shows games from a specific tournament ranked by accuracy
- `club games <slug>` — games from the last N tournaments ranked by accuracy; `--last-n` and `--min-accuracy` filters
- `club leaderboard <slug>` — annual player leaderboard by total score; `--year` and `--month` filters
- `club matchups <slug>` — head-to-head records between all club members; `--last-n` to limit scope
- `player rating-history <username> --club <slug>` — rating evolution across tournaments
- `auth login` — OAuth 2.0 PKCE + loopback (RFC 8252); tokens auto-refresh
- `auth setup` — cookie session via the Cookie Helper Chrome extension
- `auth status` — shows active credential method and validates it
- `auth clear` — removes all stored credentials
- `cache stats` — entry count, active vs. expired, database size
- `cache clear [--expired]` — purge all cache entries or only expired ones
- `--output` / `-o` flag on all data commands: `table` (default), `json`, `csv`

**Library**
- `ChessProvider` ABC — platform-agnostic interface for chess data
- `ChessComClient` — Chess.com implementation (public API + internal web endpoints)
- `ClubService`, `LeaderboardService`, `RatingHistoryService`, `MatchupService` — business logic layer
- `SQLiteCache` — disk-based HTTP cache at `~/.cache/chessclub/cache.db` with per-URL TTL
- `ChessComCookieAuth` — resolves session cookies from args, env vars, or `credentials.json`
- `ChessComOAuth` — OAuth 2.0 PKCE implementation with auto-refresh

**Tools**
- Cookie Helper Chrome extension (`tools/chessclub-cookie-helper/`) — one-click extraction of Chess.com session cookies

**Documentation**
- `README.md` — full feature overview, quick start, CLI reference, architecture diagram
- `docs/features.md` — detailed feature reference with command descriptions
- `docs/usage.md` — user guide with real output examples and Python library usage
- `docs/cache.md` — cache design, TTL policy, and implementation details
- `docs/roadmap.md` — development roadmap
- `CLAUDE.md` — comprehensive architecture guide for AI coding assistants

---

[Unreleased]: https://github.com/cmellojr/chessclub/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/cmellojr/chessclub/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/cmellojr/chessclub/releases/tag/v0.1.0
