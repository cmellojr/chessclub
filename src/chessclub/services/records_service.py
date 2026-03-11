"""Service for computing club records and highlights."""

import datetime

from chessclub.core.interfaces import ChessProvider
from chessclub.core.models import ClubRecord


class RecordsService:
    """Identifies noteworthy records across club tournaments.

    Computes records from tournament results (cheap) and optionally
    from game data (expensive, controlled by *last_n*).

    Depends only on :class:`~chessclub.core.interfaces.ChessProvider`.
    """

    def __init__(self, provider: ChessProvider):
        self.provider = provider

    def get_records(
        self,
        slug: str,
        last_n: int | None = 5,
    ) -> list[ClubRecord]:
        """Return a list of club records.

        Args:
            slug: The URL-friendly club identifier.
            last_n: Number of most recent tournaments to scan for
                game-based records (accuracy, etc.).  ``None`` or
                ``0`` scans all tournaments.  Tournament-based
                records always scan every tournament.

        Returns:
            A list of :class:`ClubRecord` instances.
        """
        tournaments = self.provider.get_club_tournaments(slug)
        tournaments.sort(key=lambda t: t.end_date or t.start_date or 0)

        records: list[ClubRecord] = []

        # --- Tournament-based records (all tournaments) ---
        records.extend(self._tournament_records(tournaments))

        # --- Game-based records (last_n tournaments) ---
        game_tournaments = tournaments
        if last_n:
            game_tournaments = tournaments[-last_n:]
        records.extend(self._game_records(game_tournaments))

        return records

    def _tournament_records(self, tournaments):
        """Compute records from tournament results."""
        if not tournaments:
            return []

        records = []

        # Collect all results across all tournaments.
        best_score = None  # (score, player, tournament_name, date)
        most_played: dict[str, int] = {}
        most_wins: dict[str, int] = {}
        biggest_tournament = None  # (player_count, name, date)

        for t in tournaments:
            ts = t.end_date or t.start_date
            results = self.provider.get_tournament_results(
                t.id,
                tournament_type=t.tournament_type,
                tournament_url=t.url,
            )

            # Biggest tournament by participant count.
            count = len(results) or t.player_count
            if biggest_tournament is None or count > biggest_tournament[0]:
                biggest_tournament = (count, t.name, ts)

            for r in results:
                key = r.player.lower()
                most_played[key] = most_played.get(key, 0) + 1
                if r.position == 1:
                    most_wins[key] = most_wins.get(key, 0) + 1
                if r.score is not None:
                    if best_score is None or r.score > best_score[0]:
                        best_score = (r.score, r.player, t.name, ts)

        # Highest single-tournament score.
        if best_score:
            records.append(ClubRecord(
                category="Highest tournament score",
                value=f"{best_score[0]:.1f} pts",
                player=best_score[1],
                detail=best_score[2],
                date=best_score[3],
            ))

        # Most tournaments played.
        if most_played:
            top = max(most_played.items(), key=lambda x: x[1])
            records.append(ClubRecord(
                category="Most tournaments played",
                value=str(top[1]),
                player=top[0],
            ))

        # Most 1st-place finishes.
        if most_wins:
            top = max(most_wins.items(), key=lambda x: x[1])
            records.append(ClubRecord(
                category="Most 1st-place finishes",
                value=str(top[1]),
                player=top[0],
            ))

        # Biggest tournament.
        if biggest_tournament:
            records.append(ClubRecord(
                category="Biggest tournament",
                value=f"{biggest_tournament[0]} players",
                player=None,
                detail=biggest_tournament[1],
                date=biggest_tournament[2],
            ))

        return records

    def _game_records(self, tournaments):
        """Compute records from game data."""
        if not tournaments:
            return []

        records = []
        best_accuracy = None  # (avg, white, black, w_acc, b_acc, url, date)
        best_player_acc = None  # (acc, player, opponent, url, date)

        for t in tournaments:
            games = self.provider.get_tournament_games(t)
            for g in games:
                if g.avg_accuracy is not None:
                    if (best_accuracy is None
                            or g.avg_accuracy > best_accuracy[0]):
                        best_accuracy = (
                            g.avg_accuracy,
                            g.white,
                            g.black,
                            g.white_accuracy,
                            g.black_accuracy,
                            g.url,
                            g.played_at,
                        )

                # Best individual accuracy.
                for acc, player, opponent in [
                    (g.white_accuracy, g.white, g.black),
                    (g.black_accuracy, g.black, g.white),
                ]:
                    if acc is not None:
                        if (best_player_acc is None
                                or acc > best_player_acc[0]):
                            best_player_acc = (
                                acc, player, opponent,
                                g.url, g.played_at,
                            )

        if best_accuracy:
            records.append(ClubRecord(
                category="Highest avg accuracy (game)",
                value=f"{best_accuracy[0]:.1f}%",
                player=f"{best_accuracy[1]} vs {best_accuracy[2]}",
                detail=(
                    f"{best_accuracy[3]:.1f}% / "
                    f"{best_accuracy[4]:.1f}%"
                ),
                date=best_accuracy[6],
            ))

        if best_player_acc:
            records.append(ClubRecord(
                category="Highest individual accuracy",
                value=f"{best_player_acc[0]:.1f}%",
                player=best_player_acc[1],
                detail=f"vs {best_player_acc[2]}",
                date=best_player_acc[4],
            ))

        return records
