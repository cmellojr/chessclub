"""Data model dataclasses shared across providers."""

from dataclasses import dataclass


# ----------------------
# Club
# ----------------------


@dataclass
class Club:
    """Represents a chess club."""

    id: str
    """URL-friendly identifier (slug)."""

    provider_id: str | None
    """Provider-specific numeric ID (e.g. Chess.com ``club_id`` field)."""

    name: str
    description: str | None
    country: str | None
    url: str | None

    members_count: int | None = None
    """Total number of club members."""

    created_at: int | None = None
    """Unix timestamp of when the club was created."""

    location: str | None = None
    """Physical location or address of the club."""

    matches_count: int | None = None
    """Number of finished team matches (events played)."""


# ----------------------
# Member
# ----------------------


@dataclass
class Member:
    """Represents a club member."""

    username: str
    rating: int | None
    title: str | None
    joined_at: int | None
    """Unix timestamp of when the member joined the club, or ``None`` if unknown."""

    activity: str | None = None
    """Activity tier reported by the provider: ``"weekly"``, ``"monthly"``,
    or ``"all_time"``.  ``None`` when not available."""


# ----------------------
# Tournament
# ----------------------


@dataclass
class Tournament:
    """Represents a tournament organised by a club."""

    id: str
    name: str
    tournament_type: str
    """Format of the event: ``"swiss"`` or ``"arena"``."""

    status: str
    """Lifecycle state: ``"finished"``, ``"in_progress"``, etc."""

    start_date: int | None
    """Unix timestamp of the event start, or ``None`` if unknown."""

    end_date: int | None
    """Unix timestamp of the event end, or ``None`` if unknown."""

    player_count: int
    winner_username: str | None
    winner_score: float | None

    club_slug: str | None = None
    """Slug of the club that organised this tournament.

    Populated when the tournament is fetched via
    :meth:`~chessclub.core.interfaces.ChessProvider.get_club_tournaments`.
    Used internally as a fallback participant source when the leaderboard
    endpoint is unavailable (e.g. Swiss format on Chess.com).
    """

    url: str | None = None
    """Public-API slug for this tournament (e.g.
    ``"my-tournament-name-12345"``).

    Used to query ``api.chess.com/pub/tournament/{url}`` for standings data.
    Populated from the ``url`` field in the provider's raw response.
    """


# ----------------------
# TournamentResult
# ----------------------


@dataclass
class TournamentResult:
    """Represents a player's result in a tournament."""

    tournament_id: str
    player: str
    position: int
    score: float | None
    rating: int | None = None
    """Player rating at the time of the tournament."""


# ----------------------
# Game
# ----------------------


@dataclass
class Game:
    """Represents a single chess game."""

    white: str
    """Username of the player with the white pieces."""

    black: str
    """Username of the player with the black pieces."""

    result: str
    """Game result: ``"1-0"``, ``"0-1"``, or ``"1/2-1/2"``."""

    opening_eco: str | None
    """ECO opening code (e.g. ``"B40"``), or ``None`` if unknown."""

    pgn: str | None
    """Full PGN string, or ``None`` if not available."""

    played_at: int | None
    """Unix timestamp of when the game was played, or ``None`` if unknown."""

    white_accuracy: float | None = None
    """Stockfish accuracy for the white player (0–100), or ``None`` if not reviewed."""

    black_accuracy: float | None = None
    """Stockfish accuracy for the black player (0–100), or ``None`` if not reviewed."""

    tournament_id: str | None = None
    """Provider-specific ID of the tournament this game belongs to."""

    url: str | None = None
    """Direct URL to the game on the provider's website."""

    @property
    def avg_accuracy(self) -> float | None:
        """Average Stockfish accuracy of both players.

        Returns:
            Mean of whichever accuracy values are present, or ``None`` if
            neither player has been reviewed.
        """
        vals = [v for v in (self.white_accuracy, self.black_accuracy)
                if v is not None]
        return sum(vals) / len(vals) if vals else None


# ----------------------
# PlayerStats
# ----------------------


@dataclass
class PlayerStats:
    """Aggregated tournament statistics for a single player."""

    username: str
    tournaments_played: int
    """Number of tournaments the player participated in."""

    wins: int
    """Number of 1st-place finishes."""

    total_score: float
    """Sum of chess scores across all qualifying tournaments."""

    avg_score: float
    """Average chess score per tournament (total_score / tournaments_played)."""


# ----------------------
# RatingSnapshot
# ----------------------


@dataclass
class RatingSnapshot:
    """A player's rating and result at one tournament.

    Used to track rating evolution over time within a club.
    """

    tournament_id: str
    """Provider-specific tournament identifier."""

    tournament_name: str
    """Display name of the tournament."""

    tournament_type: str
    """Format of the event: ``"swiss"`` or ``"arena"``."""

    tournament_date: int | None
    """Unix timestamp of the tournament end (or start as
    fallback), used for chronological ordering."""

    rating: int | None
    """Player rating at the time of the tournament."""

    position: int
    """Finishing position in the tournament."""

    score: float | None
    """Chess score achieved in the tournament."""


# ----------------------
# Matchup
# ----------------------


@dataclass
class Matchup:
    """Head-to-head record between two club members.

    Players are stored alphabetically (case-insensitive) so
    that ``player_a < player_b`` always holds.  ``wins_a``
    and ``wins_b`` correspond to those respective players.
    """

    player_a: str
    """First player (alphabetically by lowercase)."""

    player_b: str
    """Second player (alphabetically by lowercase)."""

    wins_a: int
    """Games won by ``player_a``."""

    wins_b: int
    """Games won by ``player_b``."""

    draws: int
    """Games drawn between the two players."""

    total_games: int
    """Total number of games played: wins_a + wins_b + draws."""

    last_played: int | None = None
    """Unix timestamp of the most recent game between them."""
