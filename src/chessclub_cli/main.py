"""CLI entry point for the chessclub tool.

This module is the composition root of the application.  It is the only
place that imports concrete implementations (ChessComClient, ChessComCookieAuth).
All other layers depend solely on abstractions.
"""

import webbrowser
from datetime import datetime

import requests
import typer
from rich.console import Console
from rich.table import Table

from chessclub.auth import credentials as creds_store
from chessclub.core.exceptions import AuthenticationRequiredError
from chessclub.providers.chesscom.auth import ChessComCookieAuth
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_service() -> ClubService:
    """Build and return a ClubService backed by the Chess.com provider.

    Credentials are resolved automatically by :class:`ChessComCookieAuth`
    (env vars → config file).

    Returns:
        A :class:`~chessclub.services.club_service.ClubService` instance.
    """
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
def status():
    """Show the status of configured credentials."""
    auth = ChessComCookieAuth()

    if not auth.is_authenticated():
        console.print("[yellow]No credentials configured.[/yellow]")
        console.print("Run [bold]chessclub auth setup[/bold] to configure.")
        raise typer.Exit(1)

    console.print(
        f"[green]✓ Credentials found[/green] ({auth.credential_source()})"
    )

    console.print("[dim]Validating with Chess.com...[/dim]")
    try:
        client = ChessComClient(user_agent=_USER_AGENT, auth=auth)
        client.get_club(_VALIDATION_CLUB)
        console.print("[green]✓ Credentials are valid.[/green]")
    except AuthenticationRequiredError:
        console.print("[red]✗ Credentials expired or invalid.[/red]")
        console.print("Run [bold]chessclub auth setup[/bold] to renew.")
        raise typer.Exit(1)


@auth_app.command()
def clear():
    """Remove locally saved credentials."""
    removed = creds_store.clear()
    if removed:
        console.print("[green]✓ Credentials removed.[/green]")
    else:
        console.print("[yellow]No saved credentials found.[/yellow]")


# ---------------------------------------------------------------------------
# club commands
# ---------------------------------------------------------------------------


@club_app.command()
def stats(slug: str):
    """Display the club name."""
    service = _get_service()
    print(service.get_club_name(slug))


@club_app.command()
def members(slug: str):
    """List club members."""
    service = _get_service()
    data = service.get_club_members(slug)

    table = Table(title=f"Members — {slug}")
    table.add_column("Username", style="cyan")
    for m in data:
        table.add_row(m.username)

    console.print(table)


@club_app.command()
def tournaments(slug: str):
    """List tournaments organised by the club."""
    try:
        service = _get_service()
        data = service.get_club_tournaments(slug)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

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
