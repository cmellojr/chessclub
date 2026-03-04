"""Service for computing head-to-head records between club
members."""

from chessclub.core.interfaces import ChessProvider
from chessclub.core.models import Matchup


class MatchupService:
    """Aggregates game results into head-to-head matchup
    records.

    Depends only on
    :class:`~chessclub.core.interfaces.ChessProvider` — never
    on a concrete provider implementation.

    Args:
        provider: A concrete implementation of
            :class:`ChessProvider`.
    """

    def __init__(self, provider: ChessProvider):
        self.provider = provider

    def get_matchups(
        self,
        slug: str,
        last_n: int | None = None,
    ) -> list[Matchup]:
        """Return head-to-head records for all player pairs.

        Fetches club games (optionally limited to the last *N*
        tournaments), tallies results for each unique player
        pair, and returns matchup records sorted by total
        games descending.

        Args:
            slug: The URL-friendly club identifier.
            last_n: When set, only games from the *N* most
                recent tournaments are included.  ``None``
                (default) scans every tournament.

        Returns:
            A list of :class:`Matchup` instances sorted by
            ``total_games`` descending (most active rivalries
            first).  Ties are broken alphabetically by
            ``player_a``.
        """
        games = self.provider.get_club_games(
            slug, last_n=last_n
        )

        pairs: dict[tuple[str, str], dict] = {}

        for g in games:
            w_low = g.white.lower()
            b_low = g.black.lower()
            if w_low == b_low:
                continue

            a_low, b_low_sorted = sorted([w_low, b_low])
            key = (a_low, b_low_sorted)

            if key not in pairs:
                # Preserve original casing from first
                # occurrence for display.
                if a_low == w_low:
                    a_display, b_display = g.white, g.black
                else:
                    a_display, b_display = g.black, g.white
                pairs[key] = {
                    "player_a": a_display,
                    "player_b": b_display,
                    "wins_a": 0,
                    "wins_b": 0,
                    "draws": 0,
                    "last_played": None,
                }

            entry = pairs[key]

            if g.result == "1-0":
                # White won.
                if w_low == a_low:
                    entry["wins_a"] += 1
                else:
                    entry["wins_b"] += 1
            elif g.result == "0-1":
                # Black won.
                if b_low == a_low:
                    entry["wins_a"] += 1
                else:
                    entry["wins_b"] += 1
            else:
                entry["draws"] += 1

            if g.played_at is not None:
                prev = entry["last_played"]
                if prev is None or g.played_at > prev:
                    entry["last_played"] = g.played_at

        result: list[Matchup] = []
        for entry in pairs.values():
            total = (
                entry["wins_a"]
                + entry["wins_b"]
                + entry["draws"]
            )
            result.append(Matchup(
                player_a=entry["player_a"],
                player_b=entry["player_b"],
                wins_a=entry["wins_a"],
                wins_b=entry["wins_b"],
                draws=entry["draws"],
                total_games=total,
                last_played=entry["last_played"],
            ))

        result.sort(
            key=lambda m: (
                -m.total_games,
                m.player_a.lower(),
            ),
        )
        return result
