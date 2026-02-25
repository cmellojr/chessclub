# src/chessclub/core/models.py

from dataclasses import dataclass
from typing import List, Optional


# ----------------------
# Club
# ----------------------

@dataclass
class Club:
    id: str
    name: str
    description: Optional[str]
    country: Optional[str]
    url: Optional[str]


# ----------------------
# Member
# ----------------------

@dataclass
class Member:
    username: str
    rating: Optional[int]
    title: Optional[str]
    joined_at: Optional[str]


# ----------------------
# Tournament
# ----------------------

@dataclass
class Tournament:
    id: str
    name: str
    status: str
    start_date: Optional[str]
    end_date: Optional[str]
    winner: Optional[str]


# ----------------------
# TournamentResult (future use)
# ----------------------

@dataclass
class TournamentResult:
    tournament_id: str
    player: str
    position: int
    score: Optional[float]
