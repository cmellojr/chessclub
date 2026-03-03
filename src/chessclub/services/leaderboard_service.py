"""Service for computing club leaderboards from tournament results."""

import datetime

from chessclub.core.interfaces import ChessProvider
from chessclub.core.models import PlayerStats


class LeaderboardService:
    """Aggregates tournament results into a ranked player leaderboard.

    Depends only on :class:`~chessclub.core.interfaces.ChessProvider` —
    never on a concrete provider implementation.

    Args:
        provider: A concrete implementation of :class:`ChessProvider`.
    """

    def __init__(self, provider: ChessProvider):
        self.provider = provider

    def get_leaderboard(
        self,
        slug: str,
        year: int,
        month: int | None = None,
    ) -> list[PlayerStats]:
        """Return a ranked list of player statistics for a given period.

        Fetches all club tournaments whose ``end_date`` falls within the
        requested year (and optional month), then aggregates each player's
        results across those tournaments.

        Players are sorted by ``total_score`` descending; ties are broken
        by ``wins`` descending.  Players whose leaderboard entries carry
        ``score = None`` contribute 0 to the total.

        Args:
            slug: The URL-friendly club identifier.
            year: Calendar year to filter by (uses ``Tournament.end_date``,
                falling back to ``start_date`` when ``end_date`` is absent).
            month: Optional month (1–12).  When ``None``, all months of
                *year* are included.

        Returns:
            A list of :class:`~chessclub.core.models.PlayerStats` instances
            sorted best-to-worst, or an empty list when no qualifying
            tournaments are found.
        """
        tournaments = self.provider.get_club_tournaments(slug)

        qualifying = []
        for t in tournaments:
            # Chess.com's internal API often returns end_time == 0 or omits
            # it entirely; fall back to start_date so those tournaments are
            # not silently dropped.
            ts = t.end_date or t.start_date
            if not ts:
                continue
            dt = datetime.datetime.fromtimestamp(
                ts, tz=datetime.timezone.utc
            )
            if dt.year != year:
                continue
            if month is not None and dt.month != month:
                continue
            qualifying.append(t)

        if not qualifying:
            return []

        stats: dict[str, dict] = {}

        for t in qualifying:
            results = self.provider.get_tournament_results(
                t.id, tournament_type=t.tournament_type
            )
            for r in results:
                key = r.player.lower()
                if key not in stats:
                    stats[key] = {
                        "username": r.player,
                        "tournaments_played": 0,
                        "wins": 0,
                        "total_score": 0.0,
                    }
                stats[key]["tournaments_played"] += 1
                stats[key]["total_score"] += r.score or 0.0
                if r.position == 1:
                    stats[key]["wins"] += 1

        result: list[PlayerStats] = []
        for s in stats.values():
            played = s["tournaments_played"]
            result.append(PlayerStats(
                username=s["username"],
                tournaments_played=played,
                wins=s["wins"],
                total_score=s["total_score"],
                avg_score=s["total_score"] / played if played else 0.0,
            ))

        result.sort(key=lambda p: (p.total_score, p.wins), reverse=True)
        return result
