import requests

class ChessComClient:
    BASE_URL = "https://api.chess.com/pub"

    def __init__(self, user_agent: str):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json"
        })

    def get_club(self, slug: str) -> dict:
        url = f"{self.BASE_URL}/club/{slug}"
        resp = self.session.get(url, timeout=20)
        resp.raise_for_status()
        return resp.json()