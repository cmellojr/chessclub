# src/chessclub/core/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseProvider(ABC):
    """Base interface for chess API providers."""

    def __init__(self, user_agent: str):
        self.user_agent = user_agent

    # ----------------------
    # Clubs
    # ----------------------

    @abstractmethod
    def get_club(self, club_id: str) -> Dict[str, Any]:
        """Return general information about a club."""

    @abstractmethod
    def get_club_members(self, club_id: str) -> List[Dict[str, Any]]:
        """Return the list of members for a club."""

    # ----------------------
    # Tournaments
    # ----------------------

    @abstractmethod
    def get_club_tournaments(self, club_id: str) -> List[Dict[str, Any]]:
        """List tournaments associated with a club."""

    @abstractmethod
    def get_tournament_details(self, tournament_id: str) -> Dict[str, Any]:
        """Return details for a specific tournament."""

    # ----------------------
    # Future (PGN etc.)
    # ----------------------

    @abstractmethod
    def download_tournament_pgn(self, tournament_id: str) -> str:
        """Return the full PGN for a tournament."""
