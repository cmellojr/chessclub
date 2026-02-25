"""Abstract interface for chess platform providers."""

from abc import ABC, abstractmethod

from chessclub.core.models import Club, Member, Tournament


class ChessProvider(ABC):
    """Abstract base class for chess platform API providers.

    All concrete providers (Chess.com, Lichess, …) must implement this
    interface.  The rest of the library depends exclusively on this
    abstraction — never on a specific provider implementation.
    """

    @abstractmethod
    def get_club(self, slug: str) -> Club:
        """Return general information about a club.

        Args:
            slug: The URL-friendly identifier for the club.

        Returns:
            A :class:`Club` domain model instance.
        """

    @abstractmethod
    def get_club_members(self, slug: str) -> list[Member]:
        """Return the list of members for a club.

        Args:
            slug: The URL-friendly identifier for the club.

        Returns:
            A list of :class:`Member` domain model instances.
        """

    @abstractmethod
    def get_club_tournaments(self, slug: str) -> list[Tournament]:
        """Return tournaments organised by the club.

        Args:
            slug: The URL-friendly identifier for the club.

        Returns:
            A list of :class:`Tournament` domain model instances.
        """

    @abstractmethod
    def get_player(self, username: str) -> dict:
        """Return profile information for a player.

        Args:
            username: The player's username on the platform.

        Returns:
            A dictionary with player profile data.  A ``Player`` domain model
            will be added when this feature is developed further.
        """
