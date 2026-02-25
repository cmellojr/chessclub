from abc import ABC, abstractmethod
from typing import Dict, List

class ChessProvider(ABC):

    @abstractmethod
    def get_club(self, slug: str) -> Dict:
        pass

    @abstractmethod
    def get_club_members(self, slug: str) -> List[Dict]:
        pass

    @abstractmethod
    def get_club_tournaments(self, slug: str) -> List[Dict]:
        pass

    @abstractmethod
    def get_player(self, username: str) -> Dict:
        pass