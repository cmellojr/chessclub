# chessclub — Implementation Roadmap

This file tracks the project's development plan. Mark `[x]` on completed items.
Reference with `@docs/roadmap.md` in Claude Code prompts for plan context.

---

## MVP — Core Features

### Phase 1 — Data Foundation

- [ ] Implement `--output json` on all existing CLI commands
- [ ] Implement `--output csv` on all existing CLI commands
- [ ] Add `Game` model in `core/models.py` with fields: `white`, `black`, `result`, `opening_eco`, `pgn`, `played_at`
- [ ] Implement `club tournaments <slug> --details` with full per-tournament standings (participants, position, score, rating at the time of the tournament)
- [ ] Add unit tests for new models and `--details` command

### Phase 2 — Player Aliases (multiple identities)

Players who use more than one username can be grouped under a single unified identity. All analytics services must honour these aliases automatically.

- [ ] Create `PlayerAlias` model in `core/models.py` with fields: `display_name`, `usernames: list[str]`, `provider` (to support cross-platform aliases in the future)
- [ ] Implement alias storage in `~/.config/chessclub/aliases.json` (same pattern as credentials)
- [ ] Implement management commands:
  - [ ] `chessclub alias add <display-name> <username1> <username2> ...`
  - [ ] `chessclub alias remove <display-name>`
  - [ ] `chessclub alias list`
- [ ] Implement `AliasResolver` in `services/` — a layer that resolves usernames to `display_name` before any aggregation
- [ ] Ensure `LeaderboardService`, `RatingHistoryService`, and `MatchupService` pass through `AliasResolver` before aggregating results
- [ ] Display `display_name` instead of individual usernames in CLI output when an alias exists
- [ ] Add unit tests for `AliasResolver` and management commands

### Phase 3 — Club Analytics

- [ ] Implement `LeaderboardService` in `services/` for annual points aggregation
- [ ] Implement `chessclub club leaderboard <slug> --year <year>` command with `--type arena|swiss` filter
- [ ] Implement `RatingHistoryService` to track rating evolution per tournament
- [ ] Implement `chessclub player rating-history <username> --club <slug>` command
- [ ] Implement local cache in `~/.cache/chessclub/` (JSON or SQLite) for immutable past tournament data
- [ ] Implement `MatchupService` for head-to-head records between club members
- [ ] Implement `chessclub club matchups <slug>` command with head-to-head table
- [ ] Add unit tests for each new service and command

### Phase 4 — Platform Expansion

- [ ] Implement `providers/lichess/auth.py` with API token support
- [ ] Implement `providers/lichess/client.py` satisfying the `ChessProvider` interface
- [ ] Register the Lichess provider in the composition root (`chessclub_cli/main.py`)
- [ ] Add integration tests for the Lichess provider

---

## Future Enhancements

### Phase 5 — Opening Analysis

- [ ] Integrate `python-chess` library for PGN parsing
- [ ] Implement `OpeningStatsService` to extract ECO code and opening name per game
- [ ] Implement `chessclub player openings <username> --club <slug>` command with filters for colour, time control, and opponent rating
- [ ] Implement success rate per opening (win/draw/loss rate)
- [ ] Add unit tests for opening parsing

### Phase 6 — Playing Style Profile

- [ ] Calculate average game length (number of moves)
- [ ] Identify frequency of gambits and simplification into endgame
- [ ] Implement `chessclub player profile <username>` command with a playing style fingerprint
- [ ] Add unit tests

### Phase 7 — Web Frontend (separate project: `chessclub-web`)

- [ ] Create a separate `chessclub-web` repository (Flask)
- [ ] Configure local dependency with `pip install -e ../chessclub` for development
- [ ] Implement routes and templates for the annual leaderboard
- [ ] Implement rating evolution visualisation (chart per player)
- [ ] Implement head-to-head table between members
- [ ] Implement opening statistics page per player
- [ ] Publish `chessclub` to PyPI and migrate `chessclub-web` dependency to the published version

---

## Recorded Architecture Decisions

- **Separate projects:** `chessclub` is a library/CLI; `chessclub-web` will be an independent Flask project that imports `chessclub` as a dependency.
- **Analytics layer:** new services live in `src/chessclub/analytics/` (e.g. `LeaderboardService`, `RatingHistoryService`, `OpeningStatsService`). They never depend on providers directly.
- **`Game` model:** must be added to `core/` in Phase 1 to avoid incorrect dependencies in later phases.
- **Local cache:** essential before Phase 5 — opening analysis may require hundreds of API calls.
- **Player aliases:** stored in `~/.config/chessclub/aliases.json`. The `AliasResolver` is a service layer applied before any aggregation — all analytics services receive already-resolved data. The `display_name` is the canonical player identity across all outputs.
- **Dependency rule:** `core/` imports nothing from the project. `services/` and `analytics/` import only from `core/`. No layer imports from a layer above it.