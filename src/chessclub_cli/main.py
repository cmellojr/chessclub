"""CLI entry point for the chessclub tool.

This module is the composition root of the application.  It is the only
place that imports concrete implementations (ChessComClient,
ChessComCookieAuth, ChessComOAuth).  All other layers depend solely on
abstractions.
"""

import csv
import io
import json
import os
import sys
import time
import webbrowser
from dataclasses import asdict
from datetime import datetime
from enum import Enum

# Ensure UTF-8 output on Windows where stdout may default to cp1252.
# reconfigure() is a no-op when encoding is already utf-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
import typer
from rich.console import Console
from rich.table import Table

from chessclub.auth import credentials as creds_store
from chessclub.core.exceptions import AuthenticationRequiredError
from chessclub.providers.chesscom.auth import ChessComCookieAuth, ChessComOAuth
from chessclub.providers.chesscom.client import ChessComClient
from chessclub.services.club_service import ClubService

app = typer.Typer()
club_app = typer.Typer()
auth_app = typer.Typer(help="Manage Chess.com authentication.")

app.add_typer(club_app, name="club")
app.add_typer(auth_app, name="auth")

console = Console(legacy_windows=False)

_USER_AGENT = "Chessclub/0.1 (contact: cmellojr@gmail.com)"
_VALIDATION_CLUB = "chess-com-developer-community"
_CLIENT_ID = os.getenv("CHESSCOM_CLIENT_ID", "")


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------


class OutputFormat(str, Enum):
    """Supported output formats for club commands."""

    table = "table"
    json = "json"
    csv = "csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_service() -> ClubService:
    """Build and return a ClubService backed by the Chess.com provider.

    Prefers OAuth 2.0 when a ``CHESSCOM_CLIENT_ID`` is set and an OAuth token
    file exists; falls back to :class:`ChessComCookieAuth` otherwise.

    Returns:
        A :class:`~chessclub.services.club_service.ClubService` instance.
    """
    if _CLIENT_ID and creds_store.load_oauth_token():
        auth: ChessComCookieAuth | ChessComOAuth = ChessComOAuth(
            client_id=_CLIENT_ID
        )
    else:
        auth = ChessComCookieAuth()
    provider = ChessComClient(user_agent=_USER_AGENT, auth=auth)
    return ClubService(provider)


def _fmt_date(timestamp: int | None) -> str:
    """Format a Unix timestamp as a ``YYYY-MM-DD`` string.

    Args:
        timestamp: A Unix timestamp, or ``None``.

    Returns:
        A formatted date string, or ``"—"`` when the timestamp is absent.
    """
    if timestamp is None:
        return "—"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def _to_csv(rows: list[dict], fieldnames: list[str]) -> str:
    """Serialise a list of dicts to a CSV string.

    Args:
        rows: List of dictionaries to serialise.
        fieldnames: Ordered column names.  Extra keys in ``rows`` are ignored.

    Returns:
        A CSV-formatted string including a header row.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=fieldnames, extrasaction="ignore"
    )
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# auth commands
# ---------------------------------------------------------------------------


@auth_app.command()
def setup():
    """Configure and save Chess.com credentials locally."""
    console.print("\n[bold]Chess.com credentials setup[/bold]\n")
    console.print(
        "We'll open Chess.com in your browser. "
        "Log in normally and follow the instructions below.\n"
    )

    typer.confirm(
        "Press Enter to open the browser", default=True, prompt_suffix=" "
    )
    webbrowser.open("https://www.chess.com/login")

    console.print("\n[bold]How to retrieve cookies after login:[/bold]")
    console.print(
        "  1. After logging in, click the [cyan]chessclub Cookie Helper[/cyan] "
        "icon in the browser toolbar (Chess.com knight icon)."
    )
    console.print(
        "  2. The extension shows [cyan]ACCESS_TOKEN[/cyan] and "
        "[cyan]PHPSESSID[/cyan] — copy each value and paste below.\n"
    )
    console.print(
        "[dim]No extension? Install it from "
        "[bold]tools/chessclub-cookie-helper/[/bold] "
        "(load unpacked in chrome://extensions). "
        "Or open DevTools → Application → Cookies → https://www.chess.com.[/dim]\n"
    )

    access_token = typer.prompt("Paste the ACCESS_TOKEN value", hide_input=True)
    phpsessid = typer.prompt("Paste the PHPSESSID value", hide_input=True)

    console.print("\n[dim]Validating credentials...[/dim]")
    try:
        auth = ChessComCookieAuth(
            access_token=access_token, phpsessid=phpsessid
        )
        client = ChessComClient(user_agent=_USER_AGENT, auth=auth)
        client.get_club(_VALIDATION_CLUB)
    except requests.RequestException as e:
        console.print(f"[red]Failed to validate credentials:[/red] {e}")
        raise typer.Exit(1)

    creds_store.save(access_token, phpsessid)
    console.print(
        f"[green]✓ Credentials saved to:[/green] {creds_store.credentials_path()}"
    )
    console.print(
        "[dim]ACCESS_TOKEN expires in ~24h. "
        "Run [bold]chessclub auth setup[/bold] again when needed.[/dim]\n"
    )


@auth_app.command()
def login():
    """Authenticate via OAuth 2.0 PKCE (requires Chess.com developer access)."""
    if not _CLIENT_ID:
        console.print("[red]CHESSCOM_CLIENT_ID is not set.[/red]")
        console.print(
            "Obtain a client ID by applying for Chess.com developer access,\n"
            "then set the environment variable and re-run:\n"
            "  export CHESSCOM_CLIENT_ID=<your-client-id>"
        )
        raise typer.Exit(1)
    try:
        ChessComOAuth.run_login_flow(client_id=_CLIENT_ID)
    except requests.RequestException as e:
        console.print(f"[red]Token exchange failed:[/red] {e}")
        raise typer.Exit(1)
    console.print(
        f"[green]✓ Logged in. Token saved to:[/green] "
        f"{creds_store.oauth_token_path()}"
    )


@auth_app.command()
def status():
    """Show the status of all configured credentials."""
    oauth_token = creds_store.load_oauth_token()
    cookie_auth = ChessComCookieAuth()

    if not oauth_token and not cookie_auth.is_authenticated():
        console.print("[yellow]No credentials configured.[/yellow]")
        console.print(
            "Run [bold]chessclub auth login[/bold] (OAuth 2.0) or "
            "[bold]chessclub auth setup[/bold] (session cookies)."
        )
        raise typer.Exit(1)

    if oauth_token:
        expires_at = oauth_token.get("expires_at", 0.0)
        expiry_str = datetime.fromtimestamp(expires_at).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        expired = time.time() >= expires_at
        state = "[red]expired[/red]" if expired else "[green]valid[/green]"
        console.print(
            f"[green]✓ OAuth 2.0 token[/green]  "
            f"{creds_store.oauth_token_path()}"
        )
        console.print(f"  Expires : {expiry_str} ({state})")
        if oauth_token.get("scope"):
            console.print(f"  Scopes  : {oauth_token['scope']}")

    if cookie_auth.is_authenticated():
        console.print(
            f"[green]✓ Cookie session[/green]   "
            f"{cookie_auth.credential_source()}"
        )

    # Validate whichever auth method is active.
    active_auth: ChessComCookieAuth | ChessComOAuth = (
        ChessComOAuth(client_id=_CLIENT_ID)
        if _CLIENT_ID and oauth_token
        else cookie_auth
    )

    console.print("[dim]Validating with Chess.com...[/dim]")
    try:
        client = ChessComClient(user_agent=_USER_AGENT, auth=active_auth)
        club = client.get_club(_VALIDATION_CLUB)
        # Verify session cookies against the internal API (requires auth).
        # get_club() only calls the public API and always succeeds, so we
        # must hit at least one authenticated endpoint to confirm validity.
        if club.provider_id:
            r = client.session.get(
                f"{ChessComClient.WEB_BASE_URL}/callback/clubs/live/past"
                f"/{club.provider_id}",
                params={"page": 1},
            )
            if r.status_code == 401:
                raise AuthenticationRequiredError(
                    "Session cookies are expired or invalid."
                )
            r.raise_for_status()
        console.print("[green]✓ Active credentials are valid.[/green]")
    except AuthenticationRequiredError:
        console.print("[red]✗ Credentials expired or invalid.[/red]")
        console.print(
            "Run [bold]chessclub auth login[/bold] or "
            "[bold]chessclub auth setup[/bold] to renew."
        )
        raise typer.Exit(1)


@auth_app.command()
def clear():
    """Remove all locally saved credentials (cookies and OAuth token)."""
    removed_cookies = creds_store.clear()
    removed_oauth = creds_store.clear_oauth_token()
    if removed_cookies:
        console.print("[green]✓ Cookie credentials removed.[/green]")
    if removed_oauth:
        console.print("[green]✓ OAuth token removed.[/green]")
    if not removed_cookies and not removed_oauth:
        console.print("[yellow]No saved credentials found.[/yellow]")


# ---------------------------------------------------------------------------
# club commands
# ---------------------------------------------------------------------------


@club_app.command()
def stats(
    slug: str,
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
):
    """Display club information."""
    service = _get_service()
    club = service.get_club(slug)

    if output == OutputFormat.json:
        print(json.dumps(asdict(club), indent=2))
    elif output == OutputFormat.csv:
        print(
            _to_csv(
                [asdict(club)],
                ["id", "name", "description", "country", "url"],
            ),
            end="",
        )
    else:
        console.print(club.name)


_ACTIVITY_LABEL: dict[str, str] = {
    "weekly": "This week",
    "monthly": "This month",
    "all_time": "Inactive",
}

_ACTIVITY_STYLE: dict[str, str] = {
    "weekly": "green",
    "monthly": "yellow",
    "all_time": "dim",
}


@club_app.command()
def members(
    slug: str,
    details: bool = typer.Option(
        False,
        "--details/--no-details",
        help=(
            "Fetch each member's player profile to add their title. "
            "Makes one extra API call per member — can be slow for large "
            "clubs."
        ),
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
):
    """List club members with activity tier and join date.

    Members are grouped by their last-activity tier: 'This week' (active in
    the past 7 days), 'This month' (past 30 days), or 'Inactive' (longer).

    Use --details to add chess title information (one extra API call per
    member).
    """
    service = _get_service()
    spinner_msg = (
        f"[dim]Fetching members{' and profiles' if details else ''}…[/dim]"
    )
    with console.status(spinner_msg, spinner="dots"):
        data = service.get_club_members(slug, with_details=details)

    if output == OutputFormat.json:
        print(json.dumps([asdict(m) for m in data], indent=2))
    elif output == OutputFormat.csv:
        print(
            _to_csv(
                [asdict(m) for m in data],
                ["username", "title", "activity", "joined_at"],
            ),
            end="",
        )
    else:
        table = Table(title=f"Members — {slug}", show_lines=False)
        table.add_column("Username", style="cyan")
        if details:
            table.add_column("Title", justify="center")
        table.add_column("Activity", justify="left")
        table.add_column("Joined", justify="right")

        for m in data:
            activity_label = _ACTIVITY_LABEL.get(m.activity or "", m.activity or "—")
            activity_style = _ACTIVITY_STYLE.get(m.activity or "", "")
            styled_activity = (
                f"[{activity_style}]{activity_label}[/{activity_style}]"
                if activity_style
                else activity_label
            )
            row: list[str] = [m.username]
            if details:
                row.append(m.title or "—")
            row.append(styled_activity)
            row.append(_fmt_date(m.joined_at))
            table.add_row(*row)

        console.print(table)
        console.print(f"[dim]Total: {len(data)} members[/]")


@club_app.command()
def tournaments(
    slug: str,
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
    details: bool = typer.Option(
        False,
        "--details/--no-details",
        help=(
            "Fetch and display per-player standings for each tournament. "
            "Requires authentication. Not supported with --output csv."
        ),
    ),
):
    """List tournaments organised by the club."""
    try:
        service = _get_service()
        data = service.get_club_tournaments(slug)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    if output == OutputFormat.json:
        rows = [asdict(t) for t in data]
        if details:
            for row, t in zip(rows, data):
                try:
                    results = service.get_tournament_results(
                        t.id, tournament_type=t.tournament_type
                    )
                    row["results"] = [asdict(r) for r in results]
                except AuthenticationRequiredError as e:
                    console.print(
                        f"[yellow]Warning:[/yellow] {e}", highlight=False
                    )
                    row["results"] = []
        print(json.dumps(rows, indent=2))

    elif output == OutputFormat.csv:
        if details:
            console.print(
                "[yellow]Note:[/yellow] --details is not supported with "
                "--output csv. Showing summary only."
            )
        _fields = [
            "id",
            "name",
            "tournament_type",
            "status",
            "start_date",
            "end_date",
            "player_count",
            "winner_username",
            "winner_score",
        ]
        print(_to_csv([asdict(t) for t in data], _fields), end="")

    else:
        # Default: table output
        table = Table(title=f"Tournaments — {slug}", show_lines=False)
        table.add_column("Name", style="cyan", no_wrap=False)
        table.add_column("Type", style="dim")
        table.add_column("Date", justify="right")
        table.add_column("Players", justify="right")
        table.add_column("Winner pts", justify="right")

        for t in data:
            score = str(t.winner_score) if t.winner_score is not None else "—"
            table.add_row(
                t.name,
                t.tournament_type,
                _fmt_date(t.start_date),
                str(t.player_count),
                score,
            )

        console.print(table)
        console.print(f"[dim]Total: {len(data)} tournaments[/]")

        if details:
            for t in data:
                console.rule(f"[bold]{t.name}[/bold]")
                try:
                    results = service.get_tournament_results(
                        t.id, tournament_type=t.tournament_type
                    )
                except AuthenticationRequiredError as e:
                    console.print(
                        f"  [yellow]Could not fetch standings:[/yellow] {e}",
                        highlight=False,
                    )
                    continue

                if not results:
                    console.print("  [dim]No standings available.[/dim]")
                    continue

                standings = Table(show_header=True, show_lines=False)
                standings.add_column("#", justify="right", style="dim")
                standings.add_column("Player", style="cyan")
                standings.add_column("Score", justify="right")
                standings.add_column("Rating", justify="right")

                for r in results:
                    standings.add_row(
                        str(r.position),
                        r.player,
                        str(r.score) if r.score is not None else "—",
                        str(r.rating) if r.rating is not None else "—",
                    )
                console.print(standings)


@club_app.command(name="tournament-games")
def tournament_games(
    slug: str,
    name_or_id: str = typer.Argument(
        ...,
        help=(
            "Tournament name (partial, case-insensitive) or exact numeric ID. "
            "Run 'chessclub club tournaments <slug>' to list available tournaments."
        ),
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
):
    """List all games from a specific tournament, ranked by Stockfish accuracy.

    Searches the club's tournament list for a name or ID match, then fetches
    all games played in that tournament.  If several tournaments match the
    name, the most recent one is used and a notice is printed.

    Accuracy scores require Chess.com Game Review (a Chess.com premium
    feature); games without review appear at the end with '—' in accuracy
    columns.
    """
    try:
        service = _get_service()
        with console.status(
            "[dim]Looking up tournament…[/dim]", spinner="dots"
        ):
            matches = service.find_tournaments_by_name_or_id(slug, name_or_id)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    if not matches:
        console.print(
            f"[red]Error:[/red] No tournament matching [bold]{name_or_id!r}[/bold].",
            highlight=False,
        )
        console.print(
            "[dim]Run [bold]chessclub club tournaments "
            f"{slug}[/bold] to list available tournaments.[/dim]"
        )
        raise typer.Exit(1)

    tournament = matches[0]
    if len(matches) > 1:
        console.print(
            f"[yellow]Note:[/yellow] {len(matches)} tournaments matched. "
            f"Using the most recent: [bold]{tournament.name}[/bold] "
            f"(ID: {tournament.id})"
        )
    else:
        console.print(
            f"[dim]Tournament: {tournament.name} "
            f"(ID: {tournament.id}, "
            f"{_fmt_date(tournament.start_date)}–{_fmt_date(tournament.end_date)})"
            "[/dim]"
        )

    try:
        with console.status("[dim]Fetching games…[/dim]", spinner="dots"):
            results = service.get_tournament_results(
                tournament.id, tournament_type=tournament.tournament_type
            )
            data = service.get_tournament_games(tournament)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    participant_count = len({r.player for r in results})
    with_accuracy = sum(1 for g in data if g.avg_accuracy is not None)

    def _fmt_acc(val: float | None) -> str:
        return f"{val:.1f}" if val is not None else "—"

    if output == OutputFormat.json:
        rows = []
        for g in data:
            d = asdict(g)
            d["avg_accuracy"] = g.avg_accuracy
            rows.append(d)
        print(json.dumps(rows, indent=2))

    elif output == OutputFormat.csv:
        _fields = [
            "white",
            "black",
            "result",
            "opening_eco",
            "played_at",
            "white_accuracy",
            "black_accuracy",
            "avg_accuracy",
        ]
        rows = []
        for g in data:
            d = asdict(g)
            d["avg_accuracy"] = g.avg_accuracy
            rows.append(d)
        print(_to_csv(rows, _fields), end="")

    else:
        table = Table(
            title=f"{tournament.name}", show_lines=False
        )
        table.add_column("White", style="cyan")
        table.add_column("W%", justify="right")
        table.add_column("Black", style="cyan")
        table.add_column("B%", justify="right")
        table.add_column("Avg%", justify="right", style="bold")
        table.add_column("Result", justify="center")
        table.add_column("Date", justify="right")

        for g in data:
            table.add_row(
                g.white,
                _fmt_acc(g.white_accuracy),
                g.black,
                _fmt_acc(g.black_accuracy),
                _fmt_acc(g.avg_accuracy),
                g.result,
                _fmt_date(g.played_at),
            )

        console.print(table)
        # When participant_count is 0 but games were found, the provider fell
        # back to the club member list (leaderboard endpoint unavailable).
        using_member_fallback = participant_count == 0 and len(data) > 0
        if using_member_fallback:
            participants_label = "club members (leaderboard unavailable)"
        else:
            participants_label = f"{participant_count} participants"
        console.print(
            f"[dim]Total: {len(data)} games "
            f"({with_accuracy} with accuracy data, "
            f"{participants_label})[/]"
        )
        if not data:
            if participant_count == 0:
                console.print(
                    "[yellow]Tip:[/yellow] Leaderboard returned 0 participants "
                    "and no club members could be fetched. "
                    "Check that your credentials are valid "
                    "([bold]chessclub auth setup[/bold])."
                )
            else:
                console.print(
                    f"[yellow]Tip:[/yellow] {participant_count} participants "
                    "found but no games matched the tournament time window. "
                    "This is a known Chess.com API issue — please report it."
                )


@club_app.command()
def games(
    slug: str,
    last_n: int = typer.Option(
        5,
        "--last-n",
        help=(
            "Scan only the N most recent tournaments. "
            "Use 0 to scan all tournaments (slow for large clubs)."
        ),
    ),
    min_accuracy: float = typer.Option(
        0.0,
        "--min-accuracy",
        help=(
            "Only show games where average accuracy >= this value. "
            "When > 0, games without accuracy data are also excluded."
        ),
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
):
    """List tournament games ranked by Stockfish accuracy (best first).

    Only games played inside tournaments organised by the club are included.
    Accuracy scores require Chess.com Game Review (a Chess.com premium
    feature); games without review appear at the end of the list with
    '—' in accuracy columns.

    By default only the 5 most recent tournaments are scanned. Use
    --last-n 0 to scan all tournaments (may be slow for large clubs).
    """
    n: int | None = last_n if last_n > 0 else None
    try:
        service = _get_service()
        scope = f"last {last_n} tournaments" if n else "all tournaments"
        with console.status(
            f"[dim]Fetching games ({scope})…[/dim]", spinner="dots"
        ):
            data = service.get_club_games(slug, last_n=n)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    if min_accuracy > 0:
        data = [
            g for g in data
            if g.avg_accuracy is not None and g.avg_accuracy >= min_accuracy
        ]

    with_accuracy = sum(1 for g in data if g.avg_accuracy is not None)

    def _fmt_acc(val: float | None) -> str:
        return f"{val:.1f}" if val is not None else "—"

    if output == OutputFormat.json:
        rows = []
        for g in data:
            d = asdict(g)
            d["avg_accuracy"] = g.avg_accuracy
            rows.append(d)
        print(json.dumps(rows, indent=2))

    elif output == OutputFormat.csv:
        _fields = [
            "tournament_id",
            "white",
            "black",
            "result",
            "opening_eco",
            "played_at",
            "white_accuracy",
            "black_accuracy",
            "avg_accuracy",
        ]
        rows = []
        for g in data:
            d = asdict(g)
            d["avg_accuracy"] = g.avg_accuracy
            rows.append(d)
        print(_to_csv(rows, _fields), end="")

    else:
        table = Table(
            title=f"Tournament Games — {slug}", show_lines=False
        )
        table.add_column("Tournament", style="dim", no_wrap=False)
        table.add_column("White", style="cyan")
        table.add_column("W%", justify="right")
        table.add_column("Black", style="cyan")
        table.add_column("B%", justify="right")
        table.add_column("Avg%", justify="right", style="bold")
        table.add_column("Result", justify="center")
        table.add_column("Date", justify="right")

        for g in data:
            table.add_row(
                g.tournament_id or "—",
                g.white,
                _fmt_acc(g.white_accuracy),
                g.black,
                _fmt_acc(g.black_accuracy),
                _fmt_acc(g.avg_accuracy),
                g.result,
                _fmt_date(g.played_at),
            )

        console.print(table)
        console.print(
            f"[dim]Total: {len(data)} games "
            f"({with_accuracy} with accuracy data)[/]"
        )
        if not data:
            scope_hint = (
                f"last {last_n}" if n else "all"
            )
            console.print(
                f"[yellow]Tip:[/yellow] No games were found in the {scope_hint} "
                "tournament(s). The leaderboard endpoint may not be available "
                "for those tournaments (returned 404 or 429)."
            )
            console.print(
                "[dim]• Try a larger --last-n value (e.g. --last-n 10)\n"
                "• Run [bold]chessclub club tournaments <slug>[/bold] "
                "to inspect available tournaments[/dim]"
            )
