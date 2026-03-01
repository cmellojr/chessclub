"""Chess.com provider using the public and internal web APIs."""

import datetime
import json
import re
import time
import requests

from chessclub.auth.interfaces import AuthProvider
from chessclub.core.exceptions import AuthenticationRequiredError
from chessclub.core.interfaces import ChessProvider
from chessclub.core.models import (
    Club,
    Game,
    Member,
    Tournament,
    TournamentResult,
)
from chessclub.providers.chesscom.cache import CachedResponse, SQLiteCache


class ChessComClient(ChessProvider):
    """Provider for Chess.com that combines the public API and internal endpoints.

    The public API (``api.chess.com/pub``) requires no authentication and is
    used for club metadata and member lists.  The internal web API
    (``www.chess.com/callback``) requires session cookies and is used for
    club-organised tournament data.

    Authentication is entirely optional and delegated to an
    :class:`~chessclub.auth.interfaces.AuthProvider` implementation injected
    at construction time.  The client itself has no knowledge of how
    credentials are obtained, stored, or refreshed.
    """

    BASE_URL = "https://api.chess.com/pub"
    WEB_BASE_URL = "https://www.chess.com"

    def __init__(
        self,
        user_agent: str,
        auth: AuthProvider | None = None,
    ):
        """Initialise the client.

        Args:
            user_agent: The User-Agent header value for all HTTP requests.
            auth: An optional :class:`~chessclub.auth.interfaces.AuthProvider`
                that supplies session credentials.  Required only for
                endpoints that use the internal web API (e.g. tournaments).
                When ``None``, only unauthenticated public-API endpoints are
                usable.
        """
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        })

        if auth and auth.is_authenticated():
            credentials = auth.get_credentials()
            for name, value in credentials.cookies.items():
                self.session.cookies.set(name, value, domain="www.chess.com")
            self.session.headers.update(credentials.headers)

        self._cache = SQLiteCache()

    def get_club(self, slug: str) -> Club:
        """Return general information about a club.

        Args:
            slug: The URL-friendly club identifier (e.g.
                ``"clube-de-xadrez-de-jundiai"``).

        Returns:
            A :class:`~chessclub.core.models.Club` domain model instance.

        Raises:
            requests.HTTPError: If the API returns a non-2xx status code.
        """
        r = self._cached_get(f"{self.BASE_URL}/club/{slug}")
        r.raise_for_status()
        data = r.json()
        return Club(
            id=slug,
            provider_id=str(data["club_id"]) if data.get("club_id") else None,
            name=data.get("name", ""),
            description=data.get("description"),
            country=data.get("country"),
            url=data.get("url"),
            members_count=data.get("members_count"),
            created_at=data.get("created"),
            location=data.get("location"),
        )

    def get_club_members(
        self, slug: str, with_details: bool = False
    ) -> list[Member]:
        """Return all members of a club.

        The public API groups members by activity tier (``weekly``,
        ``monthly``, ``all_time``).  All groups are merged into a single
        flat list.  Each member's ``joined_at`` and ``activity`` fields
        are always populated from the members endpoint at no extra cost.

        Args:
            slug: The URL-friendly club identifier.
            with_details: When ``True``, fetch each member's player profile
                to populate ``title``.  Adds one API call per member and
                a short sleep between requests to avoid rate-limiting.

        Returns:
            A list of :class:`~chessclub.core.models.Member` instances.

        Raises:
            requests.HTTPError: If the API returns a non-2xx status code.
        """
        r = self._cached_get(f"{self.BASE_URL}/club/{slug}/members")
        r.raise_for_status()
        data = r.json()
        members: list[Member] = []
        for group in ("weekly", "monthly", "all_time"):
            for m in data.get(group, []):
                members.append(
                    Member(
                        username=m.get("username", ""),
                        rating=None,
                        title=None,
                        joined_at=m.get("joined"),
                        activity=group,
                    )
                )

        if with_details:
            for member in members:
                try:
                    profile = self.get_player(member.username)
                    member.title = profile.get("title")
                except requests.HTTPError:
                    pass
                time.sleep(0.1)

        return members

    def get_club_tournaments(self, slug: str) -> list[Tournament]:
        """Return tournaments organised by a club.

        Uses the internal Chess.com web API which requires authentication.
        Paginates automatically until all pages are consumed.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            A list of :class:`~chessclub.core.models.Tournament` instances.

        Raises:
            AuthenticationRequiredError: If the server rejects the request
                due to missing or expired credentials.
            requests.HTTPError: If the API returns a non-2xx status code for
                reasons other than authentication.
        """
        club = self.get_club(slug)
        club_id = club.provider_id

        tournaments: list[Tournament] = []
        page = 1

        while True:
            r = self._cached_get(
                f"{self.WEB_BASE_URL}/callback/clubs/live/past/{club_id}",
                params={"page": page},
            )
            if r.status_code == 401:
                raise AuthenticationRequiredError(
                    "This endpoint requires authentication. "
                    "Run 'chessclub auth setup' to configure credentials."
                )
            r.raise_for_status()
            data = r.json()

            page_items: list[Tournament] = []
            for t in data.get("live_tournament", []):
                page_items.append(
                    self._parse_tournament(t, "swiss", club_slug=slug)
                )
            for t in data.get("arena", []):
                page_items.append(
                    self._parse_tournament(t, "arena", club_slug=slug)
                )

            if not page_items:
                break

            tournaments.extend(page_items)
            page += 1

        return tournaments

    def get_tournament_results(
        self,
        tournament_id: str,
        tournament_type: str = "arena",
    ) -> list[TournamentResult]:
        """Return per-player standings for a finished club tournament.

        Chess.com exposes different leaderboard endpoints for Swiss (live
        Swiss) and Arena formats.  This method probes the most likely URL
        first (based on ``tournament_type``) and falls back to the
        alternative pattern when the primary returns HTTP 404.

        Each URL attempt retries up to three times on HTTP 429 with
        exponential back-off (1 s, 2 s, 4 s).

        Args:
            tournament_id: The Chess.com internal tournament ID (as
                returned by :meth:`get_club_tournaments`).
            tournament_type: Either ``"swiss"`` or ``"arena"`` (default).
                Determines which leaderboard URL pattern is tried first.

        Returns:
            A list of :class:`~chessclub.core.models.TournamentResult`
            instances, or an empty list if no leaderboard is available.

        Raises:
            AuthenticationRequiredError: If the server rejects the request
                due to missing or expired credentials.
            requests.HTTPError: If the API returns an unexpected error
                status.
        """
        arena_url = (
            f"{self.WEB_BASE_URL}/callback/live/tournament"
            f"/{tournament_id}/leaderboard"
        )
        swiss_url = (
            f"{self.WEB_BASE_URL}/callback/live-tournament"
            f"/{tournament_id}/leaderboard"
        )
        urls = (
            [swiss_url, arena_url]
            if tournament_type == "swiss"
            else [arena_url, swiss_url]
        )
        for url in urls:
            result = self._try_leaderboard(url, tournament_id)
            if result is not None:
                return result
        return []

    def _try_leaderboard(
        self, url: str, tournament_id: str
    ) -> list[TournamentResult] | None:
        """Fetch a single leaderboard URL with retry logic.

        Args:
            url: The full leaderboard endpoint URL to attempt.
            tournament_id: Used to construct
                :class:`~chessclub.core.models.TournamentResult` instances.

        Returns:
            A parsed list of results on success, ``None`` when the URL
            returns HTTP 404 (caller should try the next candidate URL),
            or an empty list when rate-limiting persists after all retries.

        Raises:
            AuthenticationRequiredError: On HTTP 401.
            requests.HTTPError: On unexpected HTTP errors.
        """
        for attempt in range(3):
            r = self._cached_get(url)
            if r.status_code == 401:
                raise AuthenticationRequiredError(
                    "This endpoint requires authentication. "
                    "Run 'chessclub auth setup' to configure credentials."
                )
            if r.status_code == 404:
                return None  # Signal: try the next candidate URL.
            if r.status_code == 429:
                time.sleep(2.0 ** attempt)  # 1 s → 2 s → 4 s
                continue
            r.raise_for_status()
            break
        else:
            return []  # Persistent rate-limit; give up on this URL.

        return [
            self._parse_tournament_result(raw, tournament_id)
            for raw in r.json().get("players", [])
        ]

    def get_tournament_games(self, tournament: Tournament) -> list[Game]:
        """Return all games played inside a single club tournament.

        Resolves the tournament's participant set via the leaderboard
        endpoint, then cross-references each participant's public game
        archive for the months that overlap with the tournament window.
        Only games where both ``white`` and ``black`` are tournament
        participants and ``played_at`` falls within
        ``[tournament.start_date, tournament.end_date]`` are kept.
        Duplicate entries (the same game appearing in multiple players'
        archives) are deduplicated automatically.

        Games are sorted descending by average Stockfish accuracy; games
        without accuracy data appear last.

        Args:
            tournament: A :class:`~chessclub.core.models.Tournament`
                instance with valid ``start_date`` and ``end_date``.

        Returns:
            A list of :class:`~chessclub.core.models.Game` instances
            ordered best-to-worst by average accuracy, or an empty list
            if the leaderboard is unavailable or has no participants.

        Raises:
            AuthenticationRequiredError: If the leaderboard endpoint
                rejects the request due to missing credentials.
            requests.HTTPError: If the archive API returns an unexpected
                error status.
        """
        if tournament.start_date is None or tournament.end_date is None:
            return []

        results = self.get_tournament_results(
            tournament.id, tournament_type=tournament.tournament_type
        )
        participants = {r.player.lower() for r in results}

        if not participants and tournament.player_count > 0 and tournament.club_slug:
            # The leaderboard endpoint returned 404 (common for Swiss club
            # tournaments on Chess.com whose internal URL differs from Arena).
            # Fall back to the full club member list as the participant set.
            # All tournament participants must be club members, so games where
            # both sides are members and the timestamp falls within the
            # tournament window are very likely to be tournament games.
            members = self.get_club_members(tournament.club_slug)
            participants = {m.username.lower() for m in members}

        if not participants:
            return []

        # Chess.com's internal API often stores end_time equal to (or very
        # close to) start_time — it represents when the tournament was
        # scheduled, not when the last game finished.  We add a 6-hour buffer
        # so that games from the final rounds (which can complete after the
        # official end_time) are still captured.
        _END_BUFFER = 6 * 3600  # seconds
        effective_end = max(tournament.end_date, tournament.start_date) + _END_BUFFER

        months = self._months_in_range(
            tournament.start_date, effective_end
        )
        seen: set[str] = set()
        games: list[Game] = []

        for username in participants:
            for year, month in months:
                archive_url = (
                    f"{self.BASE_URL}/player/{username}"
                    f"/games/{year}/{month:02d}"
                )
                r = self._cached_get(archive_url)
                time.sleep(0.1)
                if r.status_code == 404:
                    continue
                r.raise_for_status()

                for raw in r.json().get("games", []):
                    end_time = raw.get("end_time")
                    if end_time is None:
                        continue
                    if not (
                        tournament.start_date
                        <= end_time
                        <= effective_end
                    ):
                        continue

                    white = (
                        raw.get("white", {}).get("username", "").lower()
                    )
                    black = (
                        raw.get("black", {}).get("username", "").lower()
                    )
                    if (
                        white not in participants
                        or black not in participants
                    ):
                        continue

                    key = (
                        raw.get("url")
                        or f"{white}:{black}:{end_time}"
                    )
                    if key in seen:
                        continue
                    seen.add(key)

                    games.append(self._parse_game(raw, tournament.id))

        games.sort(
            key=lambda g: (
                g.avg_accuracy if g.avg_accuracy is not None else -1.0
            ),
            reverse=True,
        )
        return games

    def get_club_games(
        self, slug: str, last_n: int | None = None
    ) -> list[Game]:
        """Return tournament games for a club, ranked by Stockfish accuracy.

        Fetches club tournaments, resolves each tournament's participant set,
        then queries the public game archive for each participant for the
        months that overlap with the tournament window.  Only games where both
        ``white`` and ``black`` are tournament participants and ``played_at``
        falls within ``[tournament.start_date, tournament.end_date]`` are kept.
        Duplicate entries (same game appears in multiple players' archives) are
        deduplicated automatically.

        Games are sorted descending by average Stockfish accuracy.  Games
        without accuracy data (Chess.com Game Review not run) appear last.

        Args:
            slug: The URL-friendly club identifier.
            last_n: When set, only the *N* most recent tournaments are
                scanned.  ``None`` (default) scans every tournament.

        Returns:
            A list of :class:`~chessclub.core.models.Game` instances ordered
            best-to-worst by average accuracy.

        Raises:
            AuthenticationRequiredError: If the tournament or leaderboard
                endpoints reject the request due to missing credentials.
            requests.HTTPError: If the API returns an unexpected error status.
        """
        tournaments = self.get_club_tournaments(slug)
        # Sort newest-first so that [:last_n] always selects the most recent
        # tournaments regardless of the order the API returns them.
        tournaments.sort(key=lambda t: t.end_date or 0, reverse=True)
        if last_n is not None:
            tournaments = tournaments[:last_n]

        # Aggregate games across all selected tournaments, deduplicating
        # by (white, black, played_at) in case the same game appears under
        # more than one tournament window.
        seen: set[tuple[str, str, int | None]] = set()
        all_games: list[Game] = []

        for tournament in tournaments:
            for g in self.get_tournament_games(tournament):
                key = (g.white.lower(), g.black.lower(), g.played_at)
                if key not in seen:
                    seen.add(key)
                    all_games.append(g)

        all_games.sort(
            key=lambda g: (
                g.avg_accuracy if g.avg_accuracy is not None else -1.0
            ),
            reverse=True,
        )
        return all_games

    def get_player(self, username: str) -> dict:
        """Return profile information for a player.

        Args:
            username: The player's Chess.com username.

        Returns:
            A dictionary with the raw player profile data.

        Raises:
            requests.HTTPError: If the API returns a non-2xx status code.
        """
        r = self._cached_get(f"{self.BASE_URL}/player/{username}")
        r.raise_for_status()
        return r.json()

    # -------------------------
    # Internal helpers
    # -------------------------

    @staticmethod
    def _cache_ttl(url: str) -> int | None:
        """Return the cache TTL in seconds for *url*, or ``None`` to skip.

        Rules are applied in order; the first match wins.  Only HTTP 200
        responses are ever cached — errors bypass this method entirely.

        Args:
            url: The full request URL.

        Returns:
            TTL in seconds, or ``None`` if the response must not be cached.
        """
        # Game archives: /pub/player/{u}/games/{year}/{month}
        m = re.search(r"/games/(\d{4})/(\d{2})$", url)
        if m:
            year, month = int(m.group(1)), int(m.group(2))
            now = datetime.datetime.now(datetime.timezone.utc)
            if (year, month) < (now.year, now.month):
                return 30 * 86400  # 30 days — past archives are immutable
            return 3600  # 1 hour — tournament rounds span hours, not minutes

        # Player profiles: rating/title updated at most once per day.
        if re.search(r"/pub/player/[^/]+$", url):
            return 24 * 3600  # 24 hours

        # Club member list: joins/leaves are infrequent events.
        if re.search(r"/pub/club/[^/]+/members$", url):
            return 3600  # 1 hour

        # Club info (name, description) almost never changes.
        if re.search(r"/pub/club/[^/]+$", url):
            return 24 * 3600  # 24 hours

        # Leaderboard for a finished tournament is immutable.
        if url.endswith("/leaderboard"):
            return 7 * 86400  # 7 days

        # Club tournament list: new tournaments appear weekly at most.
        if "/clubs/live/past/" in url:
            return 30 * 60  # 30 minutes

        return None  # No caching for other URLs.

    def _cached_get(
        self, url: str, **kwargs
    ) -> requests.Response | CachedResponse:
        """Perform a GET request with transparent disk-cache support.

        Consults :meth:`_cache_ttl` to decide whether to cache.  On a cache
        hit the response body is returned as a :class:`CachedResponse` stub
        (``status_code=200``, ``.json()`` works, ``.raise_for_status()`` is a
        no-op).  Only HTTP 200 responses are written to the cache; errors
        always go to the network.

        Args:
            url: Request URL.
            **kwargs: Passed verbatim to :meth:`requests.Session.get`.

        Returns:
            A live :class:`requests.Response` or a :class:`CachedResponse`
            stub.
        """
        ttl = self._cache_ttl(url)
        if ttl is None:
            return self.session.get(url, **kwargs)

        params = kwargs.get("params")
        cache_key = (
            url
            if not params
            else f"{url}?{json.dumps(params, sort_keys=True)}"
        )

        cached = self._cache.get(cache_key)
        if cached is not None:
            return CachedResponse(cached)

        r = self.session.get(url, **kwargs)
        if r.status_code == 200:
            try:
                self._cache.set(cache_key, r.json(), ttl)
            except (ValueError, OSError):
                pass
        return r

    @staticmethod
    def _parse_tournament_result(
        raw: dict, tournament_id: str
    ) -> TournamentResult:
        """Map a raw API dictionary to a TournamentResult domain model.

        Args:
            raw: The raw player entry dictionary from the leaderboard API.
            tournament_id: The tournament's provider-specific identifier.

        Returns:
            A :class:`~chessclub.core.models.TournamentResult` instance.
        """
        return TournamentResult(
            tournament_id=tournament_id,
            player=raw.get("username", ""),
            position=int(raw.get("rank", 0)),
            score=raw.get("score"),
            rating=raw.get("rating"),
        )

    @staticmethod
    def _months_in_range(
        start_ts: int, end_ts: int
    ) -> list[tuple[int, int]]:
        """Return all (year, month) pairs that overlap with a timestamp range.

        Args:
            start_ts: Unix timestamp for the start of the range (inclusive).
            end_ts: Unix timestamp for the end of the range (inclusive).

        Returns:
            An ordered list of ``(year, month)`` tuples covering every
            calendar month between *start_ts* and *end_ts*.
        """
        tz = datetime.timezone.utc
        start = datetime.datetime.fromtimestamp(start_ts, tz=tz)
        end = datetime.datetime.fromtimestamp(end_ts, tz=tz)
        months: list[tuple[int, int]] = []
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            months.append((year, month))
            month += 1
            if month > 12:
                month = 1
                year += 1
        return months

    @staticmethod
    def _parse_game(raw: dict, tournament_id: str) -> Game:
        """Map a raw Chess.com game archive entry to a Game domain model.

        Args:
            raw: The raw game dictionary from the Chess.com archive endpoint.
            tournament_id: The provider-specific tournament identifier to
                link this game back to its tournament.

        Returns:
            A :class:`~chessclub.core.models.Game` instance.
        """
        white_data = raw.get("white", {})
        black_data = raw.get("black", {})
        if white_data.get("result") == "win":
            result = "1-0"
        elif black_data.get("result") == "win":
            result = "0-1"
        else:
            result = "1/2-1/2"

        accuracies = raw.get("accuracies", {})
        return Game(
            white=white_data.get("username", ""),
            black=black_data.get("username", ""),
            result=result,
            opening_eco=raw.get("eco"),
            pgn=raw.get("pgn"),
            played_at=raw.get("end_time"),
            white_accuracy=accuracies.get("white"),
            black_accuracy=accuracies.get("black"),
            tournament_id=tournament_id,
            url=raw.get("url"),
        )

    @staticmethod
    def _parse_tournament(
        raw: dict,
        tournament_type: str,
        club_slug: str | None = None,
    ) -> Tournament:
        """Map a raw API dictionary to a Tournament domain model.

        Args:
            raw: The raw tournament dictionary from the Chess.com API.
            tournament_type: Either ``"swiss"`` or ``"arena"``.
            club_slug: The URL-friendly identifier of the club that owns
                this tournament.  Stored on the model so that
                :meth:`get_tournament_games` can fall back to the club
                member list when the leaderboard endpoint is unavailable.

        Returns:
            A :class:`~chessclub.core.models.Tournament` instance.
        """
        winner = raw.get("winner") or {}
        return Tournament(
            id=str(raw.get("id", "")),
            name=raw.get("name", ""),
            tournament_type=tournament_type,
            status="finished",
            start_date=raw.get("start_time"),
            end_date=raw.get("end_time"),
            player_count=raw.get("registered_user_count", 0),
            winner_username=winner.get("username"),
            winner_score=winner.get("score"),
            club_slug=club_slug,
        )
