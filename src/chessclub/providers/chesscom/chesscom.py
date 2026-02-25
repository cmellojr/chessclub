# src/chessclub/providers/chesscom.py

import time
import requests
from typing import List

from chessclub.core.base import BaseProvider
from chessclub.core.models import Club, Member, Tournament


BASE_URL = "https://api.chess.com/pub"


class ChessComProvider(BaseProvider):
    """
    Provider para API pública do Chess.com.
    """

    def __init__(self, user_agent: str, timeout: int = 10, max_retries: int = 3):
        super().__init__(user_agent)
        self.timeout = timeout
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent
        })

    # -------------------------
    # Internal request handler
    # -------------------------

    def _get(self, endpoint: str):
        url = f"{BASE_URL}{endpoint}"

        for attempt in range(self.max_retries):
            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()

            if response.status_code in (429, 500, 502, 503):
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue

            raise Exception(
                f"Erro HTTP {response.status_code}: {response.text}"
            )

        raise Exception("Número máximo de tentativas excedido.")

    # -------------------------
    # CLUB
    # -------------------------

    def get_club(self, club_id: str) -> Club:
        data = self._get(f"/club/{club_id}")

        return Club(
            id=club_id,
            name=data.get("name"),
            description=data.get("description"),
            country=data.get("country"),
            url=data.get("url"),
        )

    def get_club_members(self, club_id: str) -> List[Member]:
        data = self._get(f"/club/{club_id}/members")

        members = []

        # Chess.com separa por roles
        for role in ["admin", "moderator", "member"]:
            for m in data.get(role, []):
                members.append(
                    Member(
                        username=m.get("username"),
                        rating=None,  # rating não vem aqui
                        title=None,
                        joined_at=None
                    )
                )

        return members

    # -------------------------
    # TOURNAMENTS
    # -------------------------

    def get_club_tournaments(self, club_id: str) -> List[Tournament]:
        data = self._get(f"/club/{club_id}/matches")

        tournaments = []

        for match in data.get("finished", []):
            tournaments.append(
                Tournament(
                    id=str(match.get("id")),
                    name=match.get("name"),
                    status="finished",
                    start_date=match.get("start_time"),
                    end_date=match.get("end_time"),
                    winner=match.get("winner"),
                )
            )

        return tournaments

    def get_tournament_details(self, tournament_id: str) -> dict:
        """
        Retorna detalhes de um torneio específico.
        """
        data = self._get(f"/match/{tournament_id}")
        return data

    def download_tournament_pgn(self, tournament_id: str) -> str:
        """
        Retorna o PGN completo de um torneio.
        """
        data = self._get(f"/match/{tournament_id}")
        return data.get("pgn", "")