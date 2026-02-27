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
import time
import webbrowser
from dataclasses import asdict
from datetime import datetime
from enum import Enum

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

console = Console()

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
        "  1. With Chess.com open, press [cyan]F12[/cyan] to open DevTools"
    )
    console.print(
        "  2. Go to the [cyan]Application[/cyan] tab (Chrome) "
        "or [cyan]Storage[/cyan] (Firefox)"
    )
    console.print(
        "  3. In the sidebar, click "
        "[cyan]Cookies → https://www.chess.com[/cyan]"
    )
    console.print(
        "  4. Copy the value of "
        "[cyan]ACCESS_TOKEN[/cyan] and [cyan]PHPSESSID[/cyan]\n"
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
        client.get_club(_VALIDATION_CLUB)
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


@club_app.command()
def members(
    slug: str,
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
):
    """List club members."""
    service = _get_service()
    data = service.get_club_members(slug)

    if output == OutputFormat.json:
        print(json.dumps([asdict(m) for m in data], indent=2))
    elif output == OutputFormat.csv:
        print(
            _to_csv(
                [asdict(m) for m in data],
                ["username", "rating", "title", "joined_at"],
            ),
            end="",
        )
    else:
        table = Table(title=f"Members — {slug}")
        table.add_column("Username", style="cyan")
        for m in data:
            table.add_row(m.username)
        console.print(table)


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
                    results = service.get_tournament_results(t.id)
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
                    results = service.get_tournament_results(t.id)
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
