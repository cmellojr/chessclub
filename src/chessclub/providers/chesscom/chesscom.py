# src/chessclub/providers/chesscom.py

import time
import requests
from typing import List

from chessclub.core.base import BaseProvider
from chessclub.core.models import Club, Member, Tournament


BASE_URL = "https://api.chess.com/pub"


class ChessComProvider(BaseProvider):
    """Provider for the Chess.com public API."""

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
                f"HTTP error {response.status_code}: {response.text}"
            )

        raise Exception("Maximum number of retries exceeded.")

    # -------------------------
    # Club
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

        # Chess.com groups members by role
        for role in ["admin", "moderator", "member"]:
            for m in data.get(role, []):
                members.append(
                    Member(
                        username=m.get("username"),
                        rating=None,  # rating is not available from this endpoint
                        title=None,
                        joined_at=None
                    )
                )

        return members

    # -------------------------
    # Tournaments
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
        """Return details for a specific tournament."""
        data = self._get(f"/match/{tournament_id}")
        return data

    def download_tournament_pgn(self, tournament_id: str) -> str:
        """Return the full PGN for a tournament."""
        data = self._get(f"/match/{tournament_id}")
        return data.get("pgn", "")
