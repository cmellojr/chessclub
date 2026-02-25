# src/chessclub/core/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseProvider(ABC):
    """
    Interface base para provedores de APIs de xadrez.
    """

    def __init__(self, user_agent: str):
        self.user_agent = user_agent

    # ----------------------
    # Clubes
    # ----------------------

    @abstractmethod
    def get_club(self, club_id: str) -> Dict[str, Any]:
        """
        Retorna informações gerais do clube.
        """

    @abstractmethod
    def get_club_members(self, club_id: str) -> List[Dict[str, Any]]:
        """
        Retorna lista de membros do clube.
        """

    # ----------------------
    # Torneios
    # ----------------------

    @abstractmethod
    def get_club_tournaments(self, club_id: str) -> List[Dict[str, Any]]:
        """
        Lista torneios associados ao clube.
        """

    @abstractmethod
    def get_tournament_details(self, tournament_id: str) -> Dict[str, Any]:
        """
        Retorna detalhes de um torneio específico.
        """

    # ----------------------
    # Futuro (PGN etc)
    # ----------------------

    @abstractmethod
    def download_tournament_pgn(self, tournament_id: str) -> str:
        """
        Retorna o PGN completo de um torneio.
        """