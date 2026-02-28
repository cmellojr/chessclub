"""Service layer that wraps a ChessProvider for club-related operations."""

from chessclub.core.interfaces import ChessProvider
from chessclub.core.models import Club, Game, Member, Tournament, TournamentResult


class ClubService:
    """Provides business-logic methods for chess club data.

    Delegates all API calls to the injected provider so that the service
    layer remains independent of any specific chess platform.
    """

    def __init__(self, provider: ChessProvider):
        """Initialise the service.

        Args:
            provider: A concrete implementation of :class:`ChessProvider`.
        """
        self.provider = provider

    def get_club(self, slug: str) -> Club:
        """Return domain information about a club.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            A :class:`Club` domain model instance.
        """
        return self.provider.get_club(slug)

    def get_club_name(self, slug: str) -> str:
        """Return the display name of a club.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            The club's display name.
        """
        return self.provider.get_club(slug).name

    def get_club_members(
        self, slug: str, with_details: bool = False
    ) -> list[Member]:
        """Return all members of a club.

        Args:
            slug: The URL-friendly club identifier.
            with_details: When ``True``, fetch per-member profile data
                (title).  Requires one extra API call per member.

        Returns:
            A list of :class:`Member` domain model instances.
        """
        return self.provider.get_club_members(slug, with_details=with_details)

    def get_club_tournaments(self, slug: str) -> list[Tournament]:
        """Return tournaments organised by a club.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            A list of :class:`Tournament` domain model instances.
        """
        return self.provider.get_club_tournaments(slug)

    def get_tournament_results(
        self,
        tournament_id: str,
        tournament_type: str = "arena",
    ) -> list[TournamentResult]:
        """Return per-player standings for a finished tournament.

        Args:
            tournament_id: The provider-specific tournament identifier.
            tournament_type: Either ``"swiss"`` or ``"arena"`` (default).
                Passed to the provider to select the correct leaderboard
                endpoint.

        Returns:
            A list of :class:`TournamentResult` instances.
        """
        return self.provider.get_tournament_results(
            tournament_id, tournament_type=tournament_type
        )

    def find_tournaments_by_name_or_id(
        self, slug: str, name_or_id: str
    ) -> list[Tournament]:
        """Search for club tournaments by name (partial) or by exact ID.

        Performs an exact ID match first; if nothing is found it falls
        back to a case-insensitive substring match on tournament names.
        Results are ordered newest-first by ``end_date``.

        Args:
            slug: The URL-friendly club identifier.
            name_or_id: Either the exact provider tournament ID or a
                case-insensitive substring of the tournament name.

        Returns:
            A list of matching :class:`Tournament` instances, ordered
            newest-first.  An empty list means no match was found.
        """
        tournaments = self.provider.get_club_tournaments(slug)
        for t in tournaments:
            if t.id == name_or_id:
                return [t]
        query = name_or_id.lower()
        matches = [t for t in tournaments if query in t.name.lower()]
        matches.sort(key=lambda t: t.end_date or 0, reverse=True)
        return matches

    def get_tournament_games(self, tournament: Tournament) -> list[Game]:
        """Return all games played inside a single club tournament.

        Args:
            tournament: A :class:`Tournament` instance with valid
                ``start_date`` and ``end_date``.

        Returns:
            A list of :class:`Game` instances ordered best-to-worst by
            average Stockfish accuracy.
        """
        return self.provider.get_tournament_games(tournament)

    def get_club_games(
        self, slug: str, last_n: int | None = None
    ) -> list[Game]:
        """Return tournament games for a club, ranked by Stockfish accuracy.

        Args:
            slug: The URL-friendly club identifier.
            last_n: When set, only the *N* most recent tournaments are
                scanned.  ``None`` (default) scans every tournament.

        Returns:
            A list of :class:`Game` instances ordered best-to-worst by
            average Stockfish accuracy.
        """
        return self.provider.get_club_games(slug, last_n=last_n)
