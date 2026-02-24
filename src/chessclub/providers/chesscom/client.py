import requests
from chessclub.core.interfaces import ChessProvider

class ChessComClient(ChessProvider):

    BASE_URL = "https://api.chess.com/pub"

    def __init__(self, user_agent: str):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent
        })

    def get_club(self, slug: str) -> dict:
        r = self.session.get(f"{self.BASE_URL}/club/{slug}")
        r.raise_for_status()
        return r.json()

    def get_player(self, username: str) -> dict:
        r = self.session.get(f"{self.BASE_URL}/player/{username}")
        r.raise_for_status()
        return r.json()