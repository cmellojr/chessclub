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
# TournamentResult (future use)
# ----------------------


@dataclass
class TournamentResult:
    """Represents a player's result in a tournament."""

    tournament_id: str
    player: str
    position: int
    score: float | None
