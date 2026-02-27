"""Service layer that wraps a ChessProvider for club-related operations."""

from chessclub.core.interfaces import ChessProvider
from chessclub.core.models import Club, Member, Tournament, TournamentResult


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

    def get_club_members(self, slug: str) -> list[Member]:
        """Return all members of a club.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            A list of :class:`Member` domain model instances.
        """
        return self.provider.get_club_members(slug)

    def get_club_tournaments(self, slug: str) -> list[Tournament]:
        """Return tournaments organised by a club.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            A list of :class:`Tournament` domain model instances.
        """
        return self.provider.get_club_tournaments(slug)

    def get_tournament_results(
        self, tournament_id: str
    ) -> list[TournamentResult]:
        """Return per-player standings for a finished tournament.

        Args:
            tournament_id: The provider-specific tournament identifier.

        Returns:
            A list of :class:`TournamentResult` instances.
        """
        return self.provider.get_tournament_results(tournament_id)
