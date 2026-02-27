"""Unit tests for core domain models."""

from chessclub.core.models import Game, TournamentResult


class TestTournamentResult:
    def test_rating_defaults_to_none(self):
        result = TournamentResult(
            tournament_id="123",
            player="alice",
            position=1,
            score=8.0,
        )
        assert result.rating is None

    def test_rating_is_stored(self):
        result = TournamentResult(
            tournament_id="123",
            player="bob",
            position=2,
            score=7.5,
            rating=1450,
        )
        assert result.rating == 1450

    def test_score_can_be_none(self):
        result = TournamentResult(
            tournament_id="123",
            player="carol",
            position=3,
            score=None,
        )
        assert result.score is None


class TestGame:
    def test_all_fields_accessible(self):
        game = Game(
            white="alice",
            black="bob",
            result="1-0",
            opening_eco="B40",
            pgn="1. e4 c5 *",
            played_at=1700000000,
        )
        assert game.white == "alice"
        assert game.black == "bob"
        assert game.result == "1-0"
        assert game.opening_eco == "B40"
        assert game.pgn == "1. e4 c5 *"
        assert game.played_at == 1700000000

    def test_optional_fields_accept_none(self):
        game = Game(
            white="alice",
            black="bob",
            result="1/2-1/2",
            opening_eco=None,
            pgn=None,
            played_at=None,
        )
        assert game.opening_eco is None
        assert game.pgn is None
        assert game.played_at is None

    def test_black_wins_result(self):
        game = Game(
            white="alice",
            black="bob",
            result="0-1",
            opening_eco=None,
            pgn=None,
            played_at=None,
        )
        assert game.result == "0-1"
