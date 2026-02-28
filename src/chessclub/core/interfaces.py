"""Abstract interface for chess platform providers."""

from abc import ABC, abstractmethod

from chessclub.core.models import Club, Game, Member, Tournament, TournamentResult


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
    def get_club_members(
        self, slug: str, with_details: bool = False
    ) -> list[Member]:
        """Return the list of members for a club.

        Args:
            slug: The URL-friendly identifier for the club.
            with_details: When ``True``, enrich each :class:`Member` with
                additional profile data (e.g. title).  This may require
                one extra API call per member and can be slow for large clubs.

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
    def get_tournament_results(
        self,
        tournament_id: str,
        tournament_type: str = "arena",
    ) -> list[TournamentResult]:
        """Return per-player standings for a finished tournament.

        Args:
            tournament_id: The provider-specific tournament identifier.
            tournament_type: Either ``"swiss"`` or ``"arena"``.  Used to
                select the correct leaderboard endpoint when the provider
                exposes different URLs for each format.  Defaults to
                ``"arena"`` for backward compatibility.

        Returns:
            A list of :class:`TournamentResult` instances, ordered by
            position (ascending).

        Raises:
            AuthenticationRequiredError: If the endpoint requires
                authentication and no valid credentials are configured.
        """

    @abstractmethod
    def get_tournament_games(self, tournament: Tournament) -> list[Game]:
        """Return all games played inside a single club tournament.

        Only games whose participants both appear in the tournament's
        leaderboard and whose ``played_at`` timestamp falls within
        ``[tournament.start_date, tournament.end_date]`` are included.
        Results are sorted descending by average Stockfish accuracy;
        games without accuracy data appear last.

        Args:
            tournament: A :class:`Tournament` instance with valid
                ``start_date`` and ``end_date``.

        Returns:
            A list of :class:`Game` instances ordered best-to-worst by
            average accuracy, or an empty list if the leaderboard is
            unavailable.

        Raises:
            AuthenticationRequiredError: If the leaderboard endpoint
                requires authentication and no valid credentials are
                configured.
        """

    @abstractmethod
    def get_club_games(
        self, slug: str, last_n: int | None = None
    ) -> list[Game]:
        """Return games played inside tournaments organised by the club.

        Only games whose participants both appear in a club tournament's
        leaderboard and whose ``played_at`` timestamp falls within that
        tournament's ``[start_date, end_date]`` window are included.
        Results are sorted descending by average Stockfish accuracy;
        games without accuracy data appear last.

        Args:
            slug: The URL-friendly identifier for the club.
            last_n: When set, only the *N* most recent tournaments are
                scanned.  ``None`` (default) scans every tournament.

        Returns:
            A list of :class:`Game` instances ordered best-to-worst by
            average accuracy.

        Raises:
            AuthenticationRequiredError: If the tournament endpoints require
                authentication and no valid credentials are configured.
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
