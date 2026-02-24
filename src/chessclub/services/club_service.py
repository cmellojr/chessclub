from chessclub.core.interfaces import ChessProvider

class ClubService:

    def __init__(self, provider: ChessProvider):
        self.provider = provider

    def get_club_name(self, slug: str) -> str:
        data = self.provider.get_club(slug)
        return data["name"]