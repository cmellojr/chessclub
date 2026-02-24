from abc import ABC, abstractmethod
from typing import Dict

class ChessProvider(ABC):

    @abstractmethod
    def get_club(self, slug: str) -> Dict:
        pass

    @abstractmethod
    def get_player(self, username: str) -> Dict:
        pass