"""Service for computing player attendance and consistency stats."""

from chessclub.core.interfaces import ChessProvider
from chessclub.core.models import AttendanceRecord


class AttendanceService:
    """Ranks players by tournament attendance and streak consistency.

    Depends only on :class:`~chessclub.core.interfaces.ChessProvider` —
    never on a concrete provider implementation.
    """

    def __init__(self, provider: ChessProvider):
        self.provider = provider

    def get_attendance(
        self,
        slug: str,
        last_n: int | None = None,
    ) -> list[AttendanceRecord]:
        """Return attendance records sorted by participation.

        For each player who has appeared in at least one tournament,
        computes attendance percentage, current consecutive streak,
        and longest-ever streak.

        Args:
            slug: The URL-friendly club identifier.
            last_n: When set, only the *N* most recent tournaments
                are considered.  ``None`` scans every tournament.

        Returns:
            A list of :class:`AttendanceRecord` instances sorted by
            ``participation_pct`` descending, then ``max_streak``
            descending.
        """
        tournaments = self.provider.get_club_tournaments(slug)
        # Sort oldest-first so streaks are computed chronologically.
        tournaments.sort(key=lambda t: t.end_date or t.start_date or 0)

        if last_n is not None:
            tournaments = tournaments[-last_n:]

        total = len(tournaments)
        if not total:
            return []

        # Build per-player attendance bitmap (ordered oldest→newest).
        # attendance[player] = [True/False, …] per tournament index.
        attendance: dict[str, list[bool]] = {}

        for idx, t in enumerate(tournaments):
            results = self.provider.get_tournament_results(
                t.id,
                tournament_type=t.tournament_type,
                tournament_url=t.url,
            )
            seen: set[str] = set()
            for r in results:
                key = r.player.lower()
                if key in seen:
                    continue
                seen.add(key)
                if key not in attendance:
                    attendance[key] = [False] * total
                attendance[key][idx] = True

        records: list[AttendanceRecord] = []
        for player, bitmap in attendance.items():
            played = sum(bitmap)
            pct = (played / total) * 100.0

            # Current streak: count backwards from most recent.
            current = 0
            for present in reversed(bitmap):
                if present:
                    current += 1
                else:
                    break

            # Max streak.
            max_streak = 0
            streak = 0
            for present in bitmap:
                if present:
                    streak += 1
                    if streak > max_streak:
                        max_streak = streak
                else:
                    streak = 0

            records.append(
                AttendanceRecord(
                    username=player,
                    tournaments_played=played,
                    total_tournaments=total,
                    participation_pct=round(pct, 1),
                    current_streak=current,
                    max_streak=max_streak,
                )
            )

        records.sort(
            key=lambda r: (r.participation_pct, r.max_streak),
            reverse=True,
        )
        return records
