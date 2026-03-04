"""Service for tracking a player's rating evolution across
club tournaments."""

from chessclub.core.interfaces import ChessProvider
from chessclub.core.models import RatingSnapshot


class RatingHistoryService:
    """Tracks rating evolution per tournament for a player.

    Depends only on
    :class:`~chessclub.core.interfaces.ChessProvider` — never
    on a concrete provider implementation.

    Args:
        provider: A concrete implementation of
            :class:`ChessProvider`.
    """

    def __init__(self, provider: ChessProvider):
        self.provider = provider

    def get_rating_history(
        self,
        slug: str,
        username: str,
        last_n: int | None = None,
    ) -> list[RatingSnapshot]:
        """Return chronological rating snapshots for a player.

        Fetches all club tournaments, retrieves standings for
        each, and filters to entries matching *username*
        (case-insensitive).

        Args:
            slug: The URL-friendly club identifier.
            username: The player's username (matched
                case-insensitively).
            last_n: When set, only the *N* most recent
                tournaments are scanned.  ``None`` (default)
                scans every tournament.

        Returns:
            A list of :class:`RatingSnapshot` instances sorted
            by ``tournament_date`` ascending (oldest first),
            or an empty list when the player did not
            participate in any qualifying tournament.
        """
        tournaments = self.provider.get_club_tournaments(slug)

        tournaments.sort(
            key=lambda t: (t.end_date or t.start_date or 0),
        )

        if last_n is not None:
            tournaments = tournaments[-last_n:]

        target = username.lower()
        snapshots: list[RatingSnapshot] = []

        for t in tournaments:
            results = self.provider.get_tournament_results(
                t.id,
                tournament_type=t.tournament_type,
                tournament_url=t.url,
            )
            for r in results:
                if r.player.lower() != target:
                    continue
                snapshots.append(RatingSnapshot(
                    tournament_id=t.id,
                    tournament_name=t.name,
                    tournament_type=t.tournament_type,
                    tournament_date=t.end_date or t.start_date,
                    rating=r.rating,
                    position=r.position,
                    score=r.score,
                ))
                break

        return snapshots
