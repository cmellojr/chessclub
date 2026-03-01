"""Unit tests for CLI commands.

All tests use Typer's CliRunner and mock _get_service so that no real
HTTP requests are made.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from chessclub.core.models import Club, Member, Tournament, TournamentResult
from chessclub_cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_club():
    return Club(
        id="test-club",
        provider_id="42",
        name="Test Club",
        description="A test club",
        country="US",
        url="https://www.chess.com/club/test-club",
    )


@pytest.fixture()
def mock_members():
    return [
        Member(username="alice", rating=1500, title=None, joined_at=None),
        Member(username="bob", rating=1400, title=None, joined_at=None),
    ]


@pytest.fixture()
def mock_tournaments():
    return [
        Tournament(
            id="101",
            name="Spring Swiss",
            tournament_type="swiss",
            status="finished",
            start_date=1700000000,
            end_date=1700086400,
            player_count=16,
            winner_username="alice",
            winner_score=8.0,
        ),
        Tournament(
            id="102",
            name="Blitz Arena",
            tournament_type="arena",
            status="finished",
            start_date=1701000000,
            end_date=1701003600,
            player_count=10,
            winner_username="bob",
            winner_score=25.0,
        ),
    ]


@pytest.fixture()
def mock_results():
    return [
        TournamentResult(
            tournament_id="101",
            player="alice",
            position=1,
            score=8.0,
            rating=1520,
        ),
        TournamentResult(
            tournament_id="101",
            player="bob",
            position=2,
            score=7.0,
            rating=1410,
        ),
    ]


def _make_service(club, members, tournaments, results=None):
    """Return a MagicMock ClubService with canned return values."""
    svc = MagicMock()
    svc.get_club.return_value = club
    svc.get_club_members.return_value = members
    svc.get_club_tournaments.return_value = tournaments
    svc.get_tournament_results.return_value = results or []
    return svc


# ---------------------------------------------------------------------------
# stats command
# ---------------------------------------------------------------------------


def test_stats_table_output(mock_club):
    svc = _make_service(mock_club, [], [])
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(app, ["club", "stats", "test-club"])
    assert result.exit_code == 0
    assert "Test Club" in result.output


def test_stats_json_output(mock_club):
    svc = _make_service(mock_club, [], [])
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(
            app, ["club", "stats", "test-club", "--output", "json"]
        )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["name"] == "Test Club"
    assert data["id"] == "test-club"


def test_stats_csv_output(mock_club):
    svc = _make_service(mock_club, [], [])
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(
            app, ["club", "stats", "test-club", "--output", "csv"]
        )
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines[0] == (
        "id,name,description,country,url,"
        "members_count,created_at,location,matches_count"
    )
    assert "Test Club" in lines[1]


# ---------------------------------------------------------------------------
# members command
# ---------------------------------------------------------------------------


def test_members_json_output(mock_club, mock_members):
    svc = _make_service(mock_club, mock_members, [])
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(
            app, ["club", "members", "test-club", "--output", "json"]
        )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["username"] == "alice"
    assert data[1]["username"] == "bob"


def test_members_csv_output(mock_club, mock_members):
    svc = _make_service(mock_club, mock_members, [])
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(
            app, ["club", "members", "test-club", "--output", "csv"]
        )
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines[0] == "username,title,activity,joined_at"
    assert "alice" in lines[1]


# ---------------------------------------------------------------------------
# tournaments command
# ---------------------------------------------------------------------------


def test_tournaments_json_output(mock_club, mock_tournaments):
    svc = _make_service(mock_club, [], mock_tournaments)
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(
            app,
            ["club", "tournaments", "test-club", "--output", "json"],
        )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2
    assert data[0]["name"] == "Spring Swiss"
    assert data[1]["tournament_type"] == "arena"


def test_tournaments_csv_output(mock_club, mock_tournaments):
    svc = _make_service(mock_club, [], mock_tournaments)
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(
            app,
            ["club", "tournaments", "test-club", "--output", "csv"],
        )
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert "name" in lines[0]
    assert "tournament_type" in lines[0]
    assert "Spring Swiss" in lines[1]


def test_tournaments_details_calls_get_results(
    mock_club, mock_tournaments, mock_results
):
    svc = _make_service(mock_club, [], mock_tournaments, mock_results)
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(
            app,
            ["club", "tournaments", "test-club", "--details"],
        )
    assert result.exit_code == 0
    # get_tournament_results must be called once per tournament
    assert svc.get_tournament_results.call_count == len(mock_tournaments)


def test_tournaments_details_json_includes_results(
    mock_club, mock_tournaments, mock_results
):
    svc = _make_service(mock_club, [], mock_tournaments, mock_results)
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(
            app,
            [
                "club",
                "tournaments",
                "test-club",
                "--output",
                "json",
                "--details",
            ],
        )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "results" in data[0]
    assert data[0]["results"][0]["player"] == "alice"


def test_tournaments_games_flag_by_name(
    mock_club, mock_tournaments, mock_results
):
    svc = _make_service(mock_club, [], mock_tournaments, mock_results)
    svc.get_tournament_games.return_value = []
    svc.find_tournaments_by_name_or_id.return_value = [mock_tournaments[0]]
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(
            app,
            ["club", "tournaments", "test-club", "--games", "Spring Swiss"],
        )
    assert result.exit_code == 0
    svc.get_tournament_games.assert_called_once()


def test_tournaments_games_flag_by_number(
    mock_club, mock_tournaments, mock_results
):
    svc = _make_service(mock_club, [], mock_tournaments, mock_results)
    svc.get_tournament_games.return_value = []
    with patch("chessclub_cli.main._get_service", return_value=svc):
        result = runner.invoke(
            app,
            ["club", "tournaments", "test-club", "--games", "1"],
        )
    assert result.exit_code == 0
    svc.get_tournament_games.assert_called_once()
