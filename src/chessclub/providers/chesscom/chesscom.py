"""Legacy Chess.com provider backed by the public API only."""

import time

import requests

from chessclub.core.base import BaseProvider
from chessclub.core.models import Club, Member, Tournament


BASE_URL = "https://api.chess.com/pub"


class ChessComProvider(BaseProvider):
    """Provider for the Chess.com public API.

    Implements retry logic with exponential back-off for transient errors.
    This provider uses only the public API and does not require authentication.
    """

    def __init__(self, user_agent: str, timeout: int = 10, max_retries: int = 3):
        """Initialise the provider.

        Args:
            user_agent: The User-Agent header value for all HTTP requests.
            timeout: Per-request timeout in seconds.
            max_retries: Maximum number of retry attempts for transient errors.
        """
        super().__init__(user_agent)
        self.timeout = timeout
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    # -------------------------
    # Internal request handler
    # -------------------------

    def _get(self, endpoint: str):
        """Send a GET request with automatic retry on transient failures.

        Args:
            endpoint: The API path, e.g. ``"/club/my-club"``.

        Returns:
            The parsed JSON response body.

        Raises:
            requests.HTTPError: On non-retryable HTTP error responses.
            RuntimeError: When the maximum number of retries is exceeded.
        """
        url = f"{BASE_URL}{endpoint}"

        for attempt in range(self.max_retries):
            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()

            if response.status_code in (429, 500, 502, 503):
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue

            response.raise_for_status()

        raise RuntimeError("Maximum number of retries exceeded.")

    # -------------------------
    # Club
    # -------------------------

    def get_club(self, club_id: str) -> Club:
        """Return general information about a club.

        Args:
            club_id: The URL-friendly club identifier.

        Returns:
            A :class:`Club` dataclass instance.
        """
        data = self._get(f"/club/{club_id}")

        return Club(
            id=club_id,
            name=data.get("name"),
            description=data.get("description"),
            country=data.get("country"),
            url=data.get("url"),
        )

    def get_club_members(self, club_id: str) -> list[Member]:
        """Return all members of a club.

        Args:
            club_id: The URL-friendly club identifier.

        Returns:
            A list of :class:`Member` dataclass instances.
        """
        data = self._get(f"/club/{club_id}/members")

        members = []
        for role in ("admin", "moderator", "member"):
            for m in data.get(role, []):
                members.append(
                    Member(
                        username=m.get("username"),
                        rating=None,
                        title=None,
                        joined_at=None,
                    )
                )

        return members

    # -------------------------
    # Tournaments
    # -------------------------

    def get_club_tournaments(self, club_id: str) -> list[Tournament]:
        """Return finished team matches associated with a club.

        Note: the public API ``/matches`` endpoint returns club-vs-club team
        matches, not individually organised tournaments.

        Args:
            club_id: The URL-friendly club identifier.

        Returns:
            A list of :class:`Tournament` dataclass instances.
        """
        data = self._get(f"/club/{club_id}/matches")

        tournaments = []
        for match in data.get("finished", []):
            tournaments.append(
                Tournament(
                    id=str(match.get("id")),
                    name=match.get("name"),
                    status="finished",
                    start_date=match.get("start_time"),
                    end_date=match.get("end_time"),
                    winner=match.get("winner"),
                )
            )

        return tournaments

    def get_tournament_details(self, tournament_id: str) -> dict:
        """Return details for a specific tournament.

        Args:
            tournament_id: The tournament identifier.

        Returns:
            A dictionary with raw tournament data from the API.
        """
        return self._get(f"/match/{tournament_id}")

    def download_tournament_pgn(self, tournament_id: str) -> str:
        """Return the full PGN for a tournament.

        Args:
            tournament_id: The tournament identifier.

        Returns:
            A PGN string, or an empty string if no PGN is available.
        """
        data = self._get(f"/match/{tournament_id}")
        return data.get("pgn", "")
