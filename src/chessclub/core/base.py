"""Abstract base provider with HTTP retry logic."""

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Base interface for chess API providers."""

    def __init__(self, user_agent: str):
        """Initialise the provider.

        Args:
            user_agent: The User-Agent header value for HTTP requests.
        """
        self.user_agent = user_agent

    # ----------------------
    # Clubs
    # ----------------------

    @abstractmethod
    def get_club(self, club_id: str) -> dict:
        """Return general information about a club.

        Args:
            club_id: The identifier for the club.

        Returns:
            A dictionary with club data.
        """

    @abstractmethod
    def get_club_members(self, club_id: str) -> list[dict]:
        """Return the list of members for a club.

        Args:
            club_id: The identifier for the club.

        Returns:
            A list of member dictionaries.
        """

    # ----------------------
    # Tournaments
    # ----------------------

    @abstractmethod
    def get_club_tournaments(self, club_id: str) -> list[dict]:
        """List tournaments associated with a club.

        Args:
            club_id: The identifier for the club.

        Returns:
            A list of tournament dictionaries.
        """

    @abstractmethod
    def get_tournament_details(self, tournament_id: str) -> dict:
        """Return details for a specific tournament.

        Args:
            tournament_id: The identifier for the tournament.

        Returns:
            A dictionary with tournament details.
        """

    # ----------------------
    # Future (PGN etc.)
    # ----------------------

    @abstractmethod
    def download_tournament_pgn(self, tournament_id: str) -> str:
        """Return the full PGN for a tournament.

        Args:
            tournament_id: The identifier for the tournament.

        Returns:
            A PGN string with all tournament games.
        """
