import requests
from chessclub.core.interfaces import ChessProvider


class ChessComClient(ChessProvider):

    BASE_URL = "https://api.chess.com/pub"
    WEB_BASE_URL = "https://www.chess.com"

    def __init__(
        self,
        user_agent: str,
        access_token: str | None = None,
        phpsessid: str | None = None,
    ):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        })
        if access_token:
            self.session.cookies.set("ACCESS_TOKEN", access_token, domain="www.chess.com")
        if phpsessid:
            self.session.cookies.set("PHPSESSID", phpsessid, domain="www.chess.com")

    def get_club(self, slug: str) -> dict:
        r = self.session.get(f"{self.BASE_URL}/club/{slug}")
        r.raise_for_status()
        return r.json()

    def get_club_members(self, slug: str) -> list[dict]:
        r = self.session.get(f"{self.BASE_URL}/club/{slug}/members")
        r.raise_for_status()
        data = r.json()
        members = []
        for group in ("weekly", "monthly", "all_time"):
            for m in data.get(group, []):
                members.append(m)
        return members

    def get_club_tournaments(self, slug: str) -> list[dict]:
        club_data = self.get_club(slug)
        club_id = club_data["club_id"]

        tournaments: list[dict] = []
        page = 1

        while True:
            r = self.session.get(
                f"{self.WEB_BASE_URL}/callback/clubs/live/past/{club_id}",
                params={"page": page},
            )
            if r.status_code == 401:
                raise PermissionError(
                    "Autenticação necessária. "
                    "Defina as variáveis de ambiente CHESSCOM_ACCESS_TOKEN e CHESSCOM_PHPSESSID."
                )
            r.raise_for_status()
            data = r.json()

            page_items: list[dict] = []
            for t in data.get("live_tournament", []):
                t["tournament_type"] = "suíço"
                page_items.append(t)
            for t in data.get("arena", []):
                t["tournament_type"] = "arena"
                page_items.append(t)

            if not page_items:
                break

            tournaments.extend(page_items)
            page += 1

        return tournaments

    def get_player(self, username: str) -> dict:
        r = self.session.get(f"{self.BASE_URL}/player/{username}")
        r.raise_for_status()
        return r.json()
