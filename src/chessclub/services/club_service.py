"""Service layer that wraps a ChessProvider for club-related operations."""

from chessclub.core.interfaces import ChessProvider


class ClubService:
    """Provides business-logic methods for chess club data.

    Delegates all API calls to the injected provider so that the service
    layer remains independent of any specific chess platform.
    """

    def __init__(self, provider: ChessProvider):
        """Initialise the service.

        Args:
            provider: A concrete implementation of ChessProvider.
        """
        self.provider = provider

    def get_club_name(self, slug: str) -> str:
        """Return the display name of a club.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            The club's display name.
        """
        data = self.provider.get_club(slug)
        return data["name"]

    def get_club_members(self, slug: str) -> list[dict]:
        """Return all members of a club.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            A list of member dictionaries.
        """
        return self.provider.get_club_members(slug)

    def get_club_tournaments(self, slug: str) -> list[dict]:
        """Return tournaments organised by a club.

        Args:
            slug: The URL-friendly club identifier.

        Returns:
            A list of tournament dictionaries.
        """
        return self.provider.get_club_tournaments(slug)
