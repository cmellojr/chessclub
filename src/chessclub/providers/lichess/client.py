"""Lichess implementation of ChessProvider.

Covers the public Lichess REST API (https://lichess.org/api).
All endpoints used here are public — no authentication is required
unless the team is private, in which case a LichessTokenAuth instance
should be passed to the constructor.

Key differences from the Chess.com provider:

- Lichess calls clubs "teams"; the slug format is identical.
- Two tournament formats exist with separate endpoints: Swiss and Arena.
- Member lists are returned as newline-delimited JSON (ND-JSON) streams.
- Accuracy data is available only for analysed games (not all games).
- No numeric club ID resolution is needed — the slug is the primary key.
"""

import json
import time
from datetime import datetime

import requests

from chessclub.auth.interfaces import AuthProvider
from chessclub.core.exceptions import ProviderError
from chessclub.core.interfaces import ChessProvider
from chessclub.core.models import (
    Club,
    Game,
    Member,
    Tournament,
    TournamentResult,
)

# TODO: SQLiteCache lives in providers/chesscom/cache.py; it should be
# extracted to providers/cache.py as shared infrastructure once a second
# provider (this one) needs it.
from chessclub.providers.chesscom.cache import SQLiteCache

# ------------------------------------------------------------------
# TTL constants (seconds)
# ------------------------------------------------------------------

_TTL_TEAM_INFO = 24 * 3600  # team name/description rarely changes
_TTL_TEAM_MEMBERS = 3600  # joins/leaves are infrequent
_TTL_TOURNAMENT_LIST = 3600  # new tournaments appear at most weekly
_TTL_FINISHED_TOURNAMENT = 30 * 24 * 3600  # results are immutable
_TTL_GAME_ARCHIVE = 30 * 24 * 3600  # finished games are immutable
_TTL_PLAYER_PROFILE = 24 * 3600  # rating/title updated at most daily

# ------------------------------------------------------------------
# Rating time-control preference (most reliable → least reliable)
# ------------------------------------------------------------------

_RATING_PREFERENCE = (
    "rapid",
    "classical",
    "blitz",
    "bullet",
    "correspondence",
)

# ------------------------------------------------------------------
# Arena tournament status codes
# ------------------------------------------------------------------

_ARENA_STATUS: dict[int, str] = {
    10: "created",
    20: "started",
    30: "finished",
}


class LichessClient(ChessProvider):
    """Chess provider backed by the Lichess public API.

    Args:
        user_agent: HTTP User-Agent header sent with every request.
        auth: Optional auth provider for private endpoints.  Most
            operations work without authentication.
    """

    BASE_URL = "https://lichess.org/api"

    def __init__(
        self,
        user_agent: str = "chessclub/0.1.0",
        auth: AuthProvider | None = None,
    ):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": user_agent})

        if auth and auth.is_authenticated():
            credentials = auth.get_credentials()
            self._session.headers.update(credentials.headers)

        self._cache = SQLiteCache()
        self.cache_hits: int = 0
        self.network_requests: int = 0

    # ------------------------------------------------------------------
    # ChessProvider interface
    # ------------------------------------------------------------------

    def get_club(self, slug: str) -> Club:
        """Return general team information mapped to Club.

        Args:
            slug: Lichess team ID (e.g. ``"clube-campineiro-de-xadrez"``).

        Returns:
            Club domain model.

        Raises:
            ProviderError: If the team is not found or the API fails.
        """
        url = f"{self.BASE_URL}/team/{slug}"
        data = self._get_json(url, _TTL_TEAM_INFO)
        if data is None or not isinstance(data, dict):
            raise ProviderError(f"Lichess team not found: {slug}")
        return self._map_club(data, slug)

    def get_club_members(
        self, slug: str, with_details: bool = False
    ) -> list[Member]:
        """Return team members as Member objects.

        The Lichess stream includes rating and title for every user, so
        ``with_details`` has no additional network cost.

        Args:
            slug: Lichess team ID.
            with_details: Accepted for interface compatibility; ignored.

        Returns:
            List of Member objects.
        """
        url = f"{self.BASE_URL}/team/{slug}/users"
        users = self._get_ndjson(url, _TTL_TEAM_MEMBERS)
        return [self._map_member(u) for u in users]

    def get_club_tournaments(self, slug: str) -> list[Tournament]:
        """Return all tournaments organised by the team.

        Fetches both Swiss and Arena tournaments and returns them sorted
        by start date ascending (oldest first), matching the Chess.com
        provider behaviour.

        Args:
            slug: Lichess team ID.

        Returns:
            List of Tournament objects, oldest first.
        """
        swiss = self._get_swiss_tournaments(slug)
        arena = self._get_arena_tournaments(slug)
        combined = swiss + arena
        combined.sort(key=lambda t: t.start_date or 0)
        return combined

    def get_tournament_results(
        self,
        tournament_id: str,
        tournament_type: str = "arena",
        tournament_url: str | None = None,
    ) -> list[TournamentResult]:
        """Return per-player standings for a tournament.

        Args:
            tournament_id: Lichess tournament ID.
            tournament_type: ``"swiss"`` or ``"arena"``.
            tournament_url: Unused; endpoint is derived from type + ID.

        Returns:
            List of TournamentResult objects ordered by position.
        """
        if tournament_type == "swiss":
            return self._get_swiss_results(tournament_id)
        return self._get_arena_results(tournament_id)

    def get_tournament_games(
        self,
        tournament: Tournament,
        results: list[TournamentResult] | None = None,
    ) -> list[Game]:
        """Return all games played in a tournament.

        Accuracy data is included when available (requires prior game
        analysis on Lichess; many games will have ``None``).

        Args:
            tournament: Tournament domain model.
            results: Unused; Lichess returns all games via a direct
                tournament games endpoint without needing a player list.

        Returns:
            List of Game objects sorted by average accuracy descending;
            games without accuracy data appear last.
        """
        if tournament.tournament_type == "swiss":
            games = self._get_swiss_games(tournament)
        else:
            games = self._get_arena_games(tournament)
        return sorted(
            games,
            key=lambda g: g.avg_accuracy if g.avg_accuracy is not None else -1,
            reverse=True,
        )

    def get_club_games(
        self, slug: str, last_n: int | None = None
    ) -> list[Game]:
        """Return games from recent club tournaments.

        Args:
            slug: Lichess team ID.
            last_n: Number of most recent tournaments to scan.  ``None``
                scans all tournaments.

        Returns:
            Deduplicated list of Game objects sorted by average accuracy
            descending.
        """
        tournaments = self.get_club_tournaments(slug)
        if last_n:
            tournaments = tournaments[-last_n:]

        games: list[Game] = []
        seen: set[tuple] = set()

        for tournament in tournaments:
            for game in self.get_tournament_games(tournament):
                key = (game.white, game.black, game.played_at)
                if key not in seen:
                    seen.add(key)
                    games.append(game)

        return sorted(
            games,
            key=lambda g: g.avg_accuracy if g.avg_accuracy is not None else -1,
            reverse=True,
        )

    def get_player(self, username: str) -> dict:
        """Return raw player profile data from Lichess.

        Args:
            username: Lichess username.

        Returns:
            Raw API response dict.
        """
        url = f"{self.BASE_URL}/user/{username}"
        data = self._get_json(url, _TTL_PLAYER_PROFILE)
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    # Tournament helpers
    # ------------------------------------------------------------------

    def _get_swiss_tournaments(self, slug: str) -> list[Tournament]:
        """Fetch Swiss tournaments for the team.

        The endpoint returns ND-JSON (one object per line).

        Returns:
            List of Tournament objects with tournament_type ``"swiss"``.
        """
        url = f"{self.BASE_URL}/team/{slug}/swiss"
        items = self._get_ndjson(url, _TTL_TOURNAMENT_LIST)
        return [self._map_swiss_tournament(t, slug) for t in items]

    def _get_arena_tournaments(self, slug: str) -> list[Tournament]:
        """Fetch Arena tournaments for the team.

        Returns:
            List of Tournament objects with tournament_type ``"arena"``.
        """
        url = f"{self.BASE_URL}/team/{slug}/arena"
        items = self._get_ndjson(url, _TTL_TOURNAMENT_LIST)
        return [self._map_arena_tournament(t, slug) for t in items]

    def _get_swiss_results(self, tournament_id: str) -> list[TournamentResult]:
        url = f"{self.BASE_URL}/swiss/{tournament_id}/results"
        items = self._get_ndjson(url, _TTL_FINISHED_TOURNAMENT)
        return [
            TournamentResult(
                tournament_id=tournament_id,
                player=item.get("username", ""),
                position=item.get("rank", 0),
                score=item.get("points"),
                rating=item.get("rating"),
            )
            for item in items
        ]

    def _get_arena_results(self, tournament_id: str) -> list[TournamentResult]:
        url = f"{self.BASE_URL}/tournament/{tournament_id}/results"
        items = self._get_ndjson(url, _TTL_FINISHED_TOURNAMENT)
        return [
            TournamentResult(
                tournament_id=tournament_id,
                player=item.get("username", ""),
                position=item.get("rank", 0),
                score=item.get("score"),
                rating=item.get("rating"),
            )
            for item in items
        ]

    def _get_swiss_games(self, tournament: Tournament) -> list[Game]:
        url = f"{self.BASE_URL}/swiss/{tournament.id}/games"
        items = self._get_ndjson(
            url,
            _TTL_GAME_ARCHIVE,
            moves="false",
            accuracy="true",
            opening="true",
        )
        return [
            g
            for item in items
            if (g := self._map_game(item, tournament.id)) is not None
        ]

    def _get_arena_games(self, tournament: Tournament) -> list[Game]:
        url = f"{self.BASE_URL}/tournament/{tournament.id}/games"
        items = self._get_ndjson(
            url,
            _TTL_GAME_ARCHIVE,
            moves="false",
            accuracy="true",
            opening="true",
        )
        return [
            g
            for item in items
            if (g := self._map_game(item, tournament.id)) is not None
        ]

    # ------------------------------------------------------------------
    # Domain model mappers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_club(data: dict, slug: str) -> Club:
        return Club(
            id=slug,
            provider_id=None,
            name=data.get("name", slug),
            description=data.get("description"),
            country=None,
            url=f"https://lichess.org/team/{slug}",
            members_count=data.get("nbMembers"),
            created_at=LichessClient._ms_to_s(data.get("createdAt")),
            location=data.get("location"),
            matches_count=None,
        )

    @staticmethod
    def _map_member(data: dict) -> Member:
        perfs = data.get("perfs", {})
        return Member(
            username=data.get("username", ""),
            rating=LichessClient._best_rating(perfs),
            title=data.get("title"),
            joined_at=None,
            activity=LichessClient._activity_tier(data.get("seenAt")),
        )

    @staticmethod
    def _map_swiss_tournament(data: dict, slug: str) -> Tournament:
        winner = data.get("winner", {})
        winner_user = winner.get("user", {}) if winner else {}
        tid = data.get("id", "")
        return Tournament(
            id=tid,
            name=data.get("name", ""),
            tournament_type="swiss",
            status=data.get("status", "finished"),
            start_date=LichessClient._iso_to_s(data.get("startsAt")),
            end_date=LichessClient._iso_to_s(data.get("finishedAt")),
            player_count=data.get("nbPlayers", 0),
            winner_username=(winner_user.get("name") or winner_user.get("id")),
            winner_score=winner.get("points") if winner else None,
            club_slug=slug,
            url=f"https://lichess.org/swiss/{tid}",
        )

    @staticmethod
    def _map_arena_tournament(data: dict, slug: str) -> Tournament:
        status_code = data.get("status", 30)
        winner = data.get("winner", {})
        tid = data.get("id", "")
        return Tournament(
            id=tid,
            name=data.get("fullName", data.get("name", "")),
            tournament_type="arena",
            status=_ARENA_STATUS.get(
                status_code if isinstance(status_code, int) else 30,
                "finished",
            ),
            start_date=LichessClient._ms_to_s(data.get("startsAt")),
            end_date=LichessClient._ms_to_s(data.get("finishesAt")),
            player_count=data.get("nbPlayers", 0),
            winner_username=(
                winner.get("name") or winner.get("id") if winner else None
            ),
            winner_score=None,
            club_slug=slug,
            url=f"https://lichess.org/tournament/{tid}",
        )

    @staticmethod
    def _map_game(data: dict, tournament_id: str) -> Game | None:
        """Map a Lichess game object to the Game domain model.

        Args:
            data: Raw game dict from the Lichess NDJSON export.
            tournament_id: ID of the parent tournament.

        Returns:
            Game instance, or ``None`` for aborted games.
        """
        if data.get("status") == "aborted":
            return None

        players = data.get("players", {})
        white_data = players.get("white", {})
        black_data = players.get("black", {})
        white_user = white_data.get("user", {})
        black_user = black_data.get("user", {})

        white_name = white_user.get("name") or white_user.get("id", "?")
        black_name = black_user.get("name") or black_user.get("id", "?")

        opening = data.get("opening", {})
        gid = data.get("id", "")

        return Game(
            white=white_name,
            black=black_name,
            result=LichessClient._game_result(
                data.get("winner"), data.get("status", "")
            ),
            opening_eco=opening.get("eco") if opening else None,
            pgn=None,
            played_at=LichessClient._ms_to_s(data.get("createdAt")),
            white_accuracy=white_data.get("accuracy"),
            black_accuracy=black_data.get("accuracy"),
            tournament_id=tournament_id,
            url=f"https://lichess.org/{gid}",
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get_json(self, url: str, ttl: int, **params) -> dict | list | None:
        """GET a JSON endpoint with caching and rate-limit back-off.

        Args:
            url: Full endpoint URL.
            ttl: Cache TTL in seconds.
            **params: Query string parameters.

        Returns:
            Parsed JSON (dict or list) or ``None`` on error/404.
        """
        key = self._cache_key(url, params)
        cached = self._cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            if cached.get("_status") == 404:
                return None
            return cached.get("_body")

        self.network_requests += 1
        resp = self._fetch(url, params=params or None)

        if resp.status_code == 404:
            self._cache.set(key, {"_status": 404, "_body": None}, ttl)
            return None
        if resp.status_code != 200:
            return None

        body = resp.json()
        self._cache.set(key, {"_status": 200, "_body": body}, ttl)
        return body

    def _get_ndjson(self, url: str, ttl: int, **params) -> list[dict]:
        """GET an ND-JSON endpoint with caching.

        Args:
            url: Full endpoint URL.
            ttl: Cache TTL in seconds.
            **params: Query string parameters.

        Returns:
            List of parsed JSON objects, empty on error.
        """
        key = self._cache_key(url, params)
        cached = self._cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached.get("_items", [])

        self.network_requests += 1
        resp = self._fetch(
            url,
            params=params or None,
            extra_headers={"Accept": "application/x-ndjson"},
        )

        if resp.status_code != 200:
            return []

        items = self._parse_ndjson(resp.text)
        self._cache.set(key, {"_items": items}, ttl)
        return items

    def _fetch(
        self,
        url: str,
        params: dict | None = None,
        extra_headers: dict | None = None,
    ) -> requests.Response:
        """Execute GET with exponential back-off on HTTP 429.

        Args:
            url: Endpoint URL.
            params: Query string parameters.
            extra_headers: Additional headers to merge for this request.

        Returns:
            The HTTP response.
        """
        headers = extra_headers or {}
        for attempt in range(3):
            resp = self._session.get(url, params=params, headers=headers)
            if resp.status_code != 429:
                return resp
            time.sleep(2**attempt)
        return resp

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ndjson(text: str) -> list[dict]:
        """Parse a newline-delimited JSON response body.

        Args:
            text: Raw response text.

        Returns:
            List of parsed dicts; malformed lines are silently skipped.
        """
        items = []
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return items

    @staticmethod
    def _cache_key(url: str, params: dict) -> str:
        if not params:
            return url
        pairs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{url}?{pairs}"

    @staticmethod
    def _ms_to_s(ms: int | None) -> int | None:
        """Convert millisecond timestamp to seconds (Arena format)."""
        return ms // 1000 if ms is not None else None

    @staticmethod
    def _iso_to_s(iso: str | None) -> int | None:
        """Convert ISO 8601 string to Unix timestamp (Swiss format).

        Args:
            iso: Timestamp string such as ``"2026-03-29T22:30:00Z"``.

        Returns:
            Unix timestamp in seconds, or ``None`` on parse failure.
        """
        if not iso:
            return None
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _best_rating(perfs: dict) -> int | None:
        """Return the best available rating from a Lichess perfs dict.

        Args:
            perfs: The ``perfs`` field from a Lichess user object.

        Returns:
            Rating int, or ``None`` if no rated games exist.
        """
        for tc in _RATING_PREFERENCE:
            perf = perfs.get(tc, {})
            if perf.get("games", 0) > 0:
                return perf.get("rating")
        return None

    @staticmethod
    def _activity_tier(seen_at_ms: int | None) -> str | None:
        """Map a ``seenAt`` timestamp to an activity tier string.

        Args:
            seen_at_ms: Unix timestamp in milliseconds, or ``None``.

        Returns:
            ``"weekly"``, ``"monthly"``, ``"all_time"``, or ``None``.
        """
        if seen_at_ms is None:
            return None
        elapsed_days = (time.time() - seen_at_ms / 1000) / 86400
        if elapsed_days <= 7:
            return "weekly"
        if elapsed_days <= 30:
            return "monthly"
        return "all_time"

    @staticmethod
    def _game_result(winner: str | None, status: str) -> str:
        """Map Lichess winner/status to a PGN result string.

        Args:
            winner: ``"white"``, ``"black"``, or ``None`` for draws.
            status: Lichess game termination status (unused but kept
                for potential future use with stalemate/insufficient).

        Returns:
            ``"1-0"``, ``"0-1"``, or ``"1/2-1/2"``.
        """
        if winner == "white":
            return "1-0"
        if winner == "black":
            return "0-1"
        return "1/2-1/2"
