"""Data model dataclasses shared across providers."""

from dataclasses import dataclass


# ----------------------
# Club
# ----------------------


@dataclass
class Club:
    """Represents a chess club."""

    id: str
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
    status: str
    start_date: str | None
    end_date: str | None
    winner: str | None


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
