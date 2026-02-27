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


# ----------------------
# Member
# ----------------------


@dataclass
class Member:
    """Represents a club member."""

    username: str
    rating: int | None
    title: str | None
    joined_at: str | None


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
