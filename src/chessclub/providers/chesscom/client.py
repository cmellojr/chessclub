"""Chess.com provider using the public and internal web APIs."""

import requests

from chessclub.core.interfaces import ChessProvider
from chessclub.core.models import Club, Member, Tournament


class ChessComClient(ChessProvider):
    """Provider for Chess.com that combines the public API and internal endpoints.

    The public API (api.chess.com/pub) requires no authentication and is used
    for club metadata and member lists.  The internal web API
    (www.chess.com/callback) requires session cookies and is used for
    club-organised tournament data.
    """

    BASE_URL = "https://api.chess.com/pub"
    WEB_BASE_URL = "https://www.chess.com"

    def __init__(
        self,
        user_agent: str,
        access_token: str | None = None,
        phpsessid: str | None = None,
    ):
        """Initialise the client.

        Args:
            user_agent: The User-Agent header value for all HTTP requests.
            access_token: Chess.com ACCESS_TOKEN cookie value.  Required only
                for endpoints that use the internal web API.
            phpsessid: Chess.com PHPSESSID cookie value.  Required together
                with access_token for authenticated endpoints.
        """
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        })
        if access_token:
            self.session.cookies.set(
                "ACCESS_TOKEN", access_token, domain="www.chess.com"
            )
        if phpsessid:
            self.session.cookies.set(
                "PHPSESSID", phpsessid, domain="www.chess.com"
            )

    def get_club(self, slug: str) -> Club:
        """Return general information about a club.

        Args:
            slug: The URL-friendly club identifier (e.g.
                ``"clube-de-xadrez-de-jundiai"``).

        Returns:
            A :class:`Club` domain model instance.

        Raises:
            requests.HTTPError: If the API returns a non-2xx status code.
        """
        r = self.session.get(f"{self.BASE_URL}/club/{slug}")
        r.raise_for_status()
        data = r.json()
        return Club(
            id=slug,
            provider_id=str(data["club_id"]) if data.get("club_id") else None,
            name=data.get("name", ""),
            description=data.get("description"),
            country=data.get("country"),
            url=data.get("url"),
        )

    def get_club_members(self, slug: str) -> list[Member]:
        """Return all members of a club.

        The public API groups members by activity tier (weekly, monthly,
        all_time).  All groups are merged into a single flat list.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            A list of :class:`Member` domain model instances.

        Raises:
            requests.HTTPError: If the API returns a non-2xx status code.
        """
        r = self.session.get(f"{self.BASE_URL}/club/{slug}/members")
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
                        joined_at=None,
                    )
                )
        return members

    def get_club_tournaments(self, slug: str) -> list[Tournament]:
        """Return tournaments organised by a club.

        Uses the internal Chess.com web API which requires authentication
        cookies.  Paginates automatically until all pages are consumed.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            A list of :class:`Tournament` domain model instances.

        Raises:
            PermissionError: If the request is rejected due to missing or
                expired credentials.
            requests.HTTPError: If the API returns a non-2xx status code for
                reasons other than authentication.
        """
        club = self.get_club(slug)
        club_id = club.provider_id

        tournaments: list[Tournament] = []
        page = 1

        while True:
            r = self.session.get(
                f"{self.WEB_BASE_URL}/callback/clubs/live/past/{club_id}",
                params={"page": page},
            )
            if r.status_code == 401:
                raise PermissionError(
                    "Authentication required. "
                    "Set the CHESSCOM_ACCESS_TOKEN and CHESSCOM_PHPSESSID "
                    "environment variables, or run 'chessclub auth setup'."
                )
            r.raise_for_status()
            data = r.json()

            page_items: list[Tournament] = []
            for t in data.get("live_tournament", []):
                page_items.append(self._parse_tournament(t, "swiss"))
            for t in data.get("arena", []):
                page_items.append(self._parse_tournament(t, "arena"))

            if not page_items:
                break

            tournaments.extend(page_items)
            page += 1

        return tournaments

    def get_player(self, username: str) -> dict:
        """Return profile information for a player.

        Args:
            username: The player's Chess.com username.

        Returns:
            A dictionary with the raw player profile data.

        Raises:
            requests.HTTPError: If the API returns a non-2xx status code.
        """
        r = self.session.get(f"{self.BASE_URL}/player/{username}")
        r.raise_for_status()
        return r.json()

    # -------------------------
    # Internal helpers
    # -------------------------

    @staticmethod
    def _parse_tournament(raw: dict, tournament_type: str) -> Tournament:
        """Map a raw API dictionary to a :class:`Tournament` domain model.

        Args:
            raw: The raw tournament dictionary from the Chess.com API.
            tournament_type: Either ``"swiss"`` or ``"arena"``.

        Returns:
            A :class:`Tournament` domain model instance.
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
        )
