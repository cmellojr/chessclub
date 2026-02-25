"""Abstract interface for chess platform providers."""

from abc import ABC, abstractmethod


class ChessProvider(ABC):
    """Abstract base class for chess platform API providers."""

    @abstractmethod
    def get_club(self, slug: str) -> dict:
        """Return general information about a club.

        Args:
            slug: The URL-friendly identifier for the club.

        Returns:
            A dictionary with club data from the provider.
        """

    @abstractmethod
    def get_club_members(self, slug: str) -> list[dict]:
        """Return the list of members for a club.

        Args:
            slug: The URL-friendly identifier for the club.

        Returns:
            A list of member dictionaries.
        """

    @abstractmethod
    def get_club_tournaments(self, slug: str) -> list[dict]:
        """Return tournaments organised by the club.

        Args:
            slug: The URL-friendly identifier for the club.

        Returns:
            A list of tournament dictionaries.
        """

    @abstractmethod
    def get_player(self, username: str) -> dict:
        """Return profile information for a player.

        Args:
            username: The player's username on the platform.

        Returns:
            A dictionary with player profile data.
        """
