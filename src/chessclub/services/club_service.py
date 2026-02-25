from chessclub.core.interfaces import ChessProvider

class ClubService:

    def __init__(self, provider: ChessProvider):
        self.provider = provider

    def get_club_name(self, slug: str) -> str:
        data = self.provider.get_club(slug)
        return data["name"]

    def get_club_members(self, slug: str) -> list[dict]:
        return self.provider.get_club_members(slug)

    def get_club_tournaments(self, slug: str) -> list[dict]:
        return self.provider.get_club_tournaments(slug)