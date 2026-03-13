"""CLI entry point for the chessclub tool.

This module is the composition root of the application.  It is the only
place that imports concrete implementations (ChessComClient,
ChessComCookieAuth, ChessComOAuth).  All other layers depend solely on
abstractions.
"""

import contextlib
import csv
import functools
import io
import json
import os
import re
import sys
import textwrap
import time
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum

# Ensure UTF-8 output on Windows where stdout may default to cp1252.
# reconfigure() is a no-op when encoding is already utf-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
import typer
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from chessclub.auth import credentials as creds_store
from chessclub.core.exceptions import AuthenticationRequiredError
from chessclub.providers.chesscom.auth import ChessComCookieAuth, ChessComOAuth
from chessclub.providers.chesscom.client import ChessComClient
from chessclub.services.club_service import ClubService


class Provider(str, Enum):
    """Supported chess platforms."""

    chesscom = "chesscom"
    lichess = "lichess"


class OutputFormat(str, Enum):
    """Supported output formats for club commands."""

    table = "table"
    json = "json"
    csv = "csv"


app = typer.Typer()
club_app = typer.Typer()
auth_app = typer.Typer(help="Manage Chess.com authentication.")
cache_app = typer.Typer(help="Manage the API response cache.")
player_app = typer.Typer(help="Player-specific analytics.")


@app.callback()
def _main_callback(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show timing, cache/network stats, and auth method.",
    ),
    provider: Provider = typer.Option(
        Provider.chesscom,
        "--provider",
        "-p",
        help="Platform to use: chesscom (default) or lichess.",
    ),
) -> None:
    """Chessclub — CLI for chess platform analytics."""
    global _verbose, _provider_name
    _verbose = verbose
    _provider_name = provider.value


app.add_typer(club_app, name="club")
app.add_typer(auth_app, name="auth")
app.add_typer(cache_app, name="cache")
app.add_typer(player_app, name="player")

console = Console(legacy_windows=False)

_USER_AGENT = "Chessclub/0.2 (contact: cmellojr@gmail.com)"
_VALIDATION_CLUB = "chess-com-developer-community"
_ENV_CLIENT_ID = "CHESSCOM_CLIENT_ID"

_current_provider: ChessComClient | None = None
_verbose: bool = False
_provider_name: str = "chesscom"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_footer(elapsed: float) -> None:
    """Print elapsed time, cache/network stats, and auth info.

    Only prints when ``--verbose`` / ``-v`` is active.
    """
    if not _verbose:
        return
    parts = [f"{elapsed:.1f}s"]
    if _current_provider:
        hits = _current_provider.cache_hits
        net = _current_provider.network_requests
        if hits and not net:
            parts.append("from cache")
        elif hits and net:
            parts.append(f"{hits} cache / {net} network")
        # Auth method summary.
        if _provider_name == "lichess":
            sess = getattr(_current_provider, "_session", None)
            if sess and "Authorization" in sess.headers:
                parts.append("auth: token")
        else:
            has_cookie = bool(_current_provider.session.cookies)
            has_oauth = "Authorization" in _current_provider.session.headers
            if has_cookie and has_oauth:
                parts.append("auth: cookie + OAuth")
            elif has_cookie:
                parts.append("auth: cookie")
            elif has_oauth:
                parts.append("auth: OAuth")
    console.print(f"\n[dim]{' · '.join(parts)}[/dim]")


def _timed(func):
    """Decorator that prints elapsed time and cache stats after a command."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global _current_provider
        _current_provider = None
        t0 = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - t0
            _print_footer(elapsed)

    return wrapper


def _resolve_client_id() -> str:
    """Resolve the OAuth client ID from available sources.

    Resolution order:

    1. ``CHESSCOM_CLIENT_ID`` environment variable (allows override).
    2. ``client_id`` stored in ``oauth_token.json`` (persisted after
       ``auth login``).

    Returns:
        The client ID string, or an empty string if unavailable.
    """
    env_id = os.getenv(_ENV_CLIENT_ID, "")
    if env_id:
        return env_id
    token = creds_store.load_oauth_token()
    if token and token.get("client_id"):
        return token["client_id"]
    return ""


def _get_service() -> ClubService:
    """Build and return a ClubService backed by the selected provider.

    When ``--provider lichess`` is active, returns a ClubService backed
    by :class:`~chessclub.providers.lichess.client.LichessClient`.
    Otherwise defaults to Chess.com, preferring OAuth 2.0 when a client
    ID is available; falls back to :class:`ChessComCookieAuth`.

    Returns:
        A :class:`~chessclub.services.club_service.ClubService` instance.
    """
    global _current_provider
    if _provider_name == "lichess":
        from chessclub.providers.lichess.auth import LichessTokenAuth
        from chessclub.providers.lichess.client import LichessClient

        auth = LichessTokenAuth()
        provider = LichessClient(user_agent=_USER_AGENT, auth=auth)
        _current_provider = provider
        return ClubService(provider)
    client_id = _resolve_client_id()
    use_oauth = client_id and creds_store.load_oauth_token()
    cookie_auth = ChessComCookieAuth()
    # Always use cookies as the base auth — /callback/ endpoints
    # require session cookies and reject OAuth Bearer tokens.
    provider = ChessComClient(user_agent=_USER_AGENT, auth=cookie_auth)
    _current_provider = provider
    if use_oauth:
        # Additionally set the OAuth Bearer header for endpoints
        # that accept it (e.g. auth status validation).
        oauth_auth = ChessComOAuth(client_id=client_id)
        oauth_creds = oauth_auth.get_credentials()
        provider.session.headers.update(oauth_creds.headers)
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


def _fmt_acc(val: float | None) -> str:
    """Format a Stockfish accuracy value as a 1-decimal string.

    Args:
        val: Accuracy (0–100), or ``None``.

    Returns:
        A formatted string like ``"87.3"``, or ``"—"`` when absent.
    """
    return f"{val:.1f}" if val is not None else "—"


def _to_csv(rows: list[dict], fieldnames: list[str]) -> str:
    """Serialise a list of dicts to a CSV string.

    Args:
        rows: List of dictionaries to serialise.
        fieldnames: Ordered column names.  Extra keys in ``rows`` are ignored.

    Returns:
        A CSV-formatted string including a header row.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# auth commands
# ---------------------------------------------------------------------------


@auth_app.command()
@_timed
def setup():
    """Configure and save Chess.com credentials locally."""
    console.print("\n[bold]Chess.com credentials setup[/bold]\n")
    console.print(
        "Use the [cyan]chessclub Cookie Helper[/cyan] extension "
        "to copy the cookies from Chess.com.\n"
    )
    console.print(
        "  1. Log in at [link=https://www.chess.com]chess.com[/link] "
        "if you haven't already."
    )
    console.print(
        "  2. Click the [cyan]chessclub Cookie Helper[/cyan] "
        "icon in the browser toolbar."
    )
    console.print(
        "  3. Copy [cyan]ACCESS_TOKEN[/cyan] and "
        "[cyan]PHPSESSID[/cyan] and paste below.\n"
    )
    console.print(
        "[dim]No extension? Install it from "
        "[bold]tools/chessclub-cookie-helper/[/bold] "
        "(load unpacked in chrome://extensions).[/dim]\n"
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
@_timed
def login():
    """Authenticate via OAuth 2.0 PKCE (requires Chess.com developer access)."""
    client_id = _resolve_client_id()
    if not client_id:
        console.print("[red]No client_id found.[/red]\n")
        console.print(
            "Each user must obtain their own client_id from Chess.com:\n"
        )
        console.print(
            "  1. Join the Chess.com Developer Community\n"
            "     https://www.chess.com/club/"
            "chess-com-developer-community\n"
            "  2. Submit the OAuth Application Form\n"
            "     https://forms.gle/RwGLuZkwDysCj2GV7\n"
            "  3. Set the environment variable:\n"
            "     [bold]export CHESSCOM_CLIENT_ID="
            "<your-client-id>[/bold]\n"
            "  4. Re-run [bold]chessclub auth login[/bold]"
        )
        raise typer.Exit(1)
    try:
        ChessComOAuth.run_login_flow(client_id=client_id)
    except requests.RequestException as e:
        console.print(f"[red]Token exchange failed:[/red] {e}")
        raise typer.Exit(1)
    console.print(
        f"[green]✓ Logged in. Token saved to:[/green] "
        f"{creds_store.oauth_token_path()}"
    )
    console.print(
        "[dim]The client_id was saved with the token — "
        "no need to set the environment variable again.[/dim]"
    )


@auth_app.command()
@_timed
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

    # Validate the active auth method.
    client_id = _resolve_client_id()
    use_oauth = bool(client_id and oauth_token)

    if use_oauth:
        # OAuth tokens are validated locally — the /callback/ endpoints
        # only accept session cookies, not Bearer tokens, so a network
        # check would always fail.
        oauth_auth = ChessComOAuth(client_id=client_id)
        if oauth_auth.is_authenticated():
            console.print(
                "[green]✓ OAuth token is valid (local check).[/green]"
            )
        else:
            console.print("[red]✗ OAuth token expired or invalid.[/red]")
            console.print("Run [bold]chessclub auth login[/bold] to renew.")
            raise typer.Exit(1)
    else:
        # Cookie session — validate against an authenticated endpoint.
        console.print("[dim]Validating with Chess.com...[/dim]")
        try:
            client = ChessComClient(user_agent=_USER_AGENT, auth=cookie_auth)
            club = client.get_club(_VALIDATION_CLUB)
            if club.provider_id:
                r = client.session.get(
                    f"{ChessComClient.WEB_BASE_URL}"
                    f"/callback/clubs/live/past"
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
@_timed
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
@_timed
def stats(
    slug: str,
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
):
    """Display club information."""
    service = _get_service()
    club = service.get_club(slug)

    # Tournament count requires auth; omit silently if unavailable.
    tournaments_count: int | None = None
    with contextlib.suppress(AuthenticationRequiredError, Exception):
        tournaments_count = len(service.get_club_tournaments(slug))

    club.matches_count = tournaments_count

    if output == OutputFormat.json:
        print(json.dumps(asdict(club), indent=2))
    elif output == OutputFormat.csv:
        print(
            _to_csv(
                [asdict(club)],
                [
                    "id",
                    "name",
                    "description",
                    "country",
                    "url",
                    "members_count",
                    "created_at",
                    "location",
                    "matches_count",
                ],
            ),
            end="",
        )
    else:
        # Country URL → flag emoji (e.g. ".../country/BR" → "🇧🇷")
        def _flag(country_url: str | None) -> str:
            """Convert a country URL to a flag emoji."""
            if not country_url:
                return ""
            code = country_url.rstrip("/").split("/")[-1].upper()
            if len(code) != 2 or not code.isalpha():
                return ""
            return "".join(chr(0x1F1E0 + ord(c) - ord("A")) for c in code)

        # Strip HTML tags; convert <br> to newline first
        def _strip_html(html: str | None) -> str:
            """Strip HTML tags, converting ``<br>`` to newlines."""
            if not html:
                return ""
            text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
            text = re.sub(r"<[^>]+>", "", text)
            return text.strip()

        _WIDTH = 80

        flag = _flag(club.country)
        title = f"{flag} {club.name}" if flag else club.name
        console.print(
            Panel(
                Align.center(f"[bold]{title}[/bold]"),
                padding=(0, 2),
                width=_WIDTH,
            )
        )

        stats_parts: list[str] = []
        if club.members_count is not None:
            stats_parts.append(f"[cyan]{club.members_count}[/cyan] Membros")
        if club.created_at is not None:
            dt = datetime.fromtimestamp(club.created_at, tz=timezone.utc)
            stats_parts.append(
                f"Criado em [cyan]{dt.strftime('%d/%m/%Y')}[/cyan]"
            )
        if club.matches_count is not None:
            stats_parts.append(f"[cyan]{club.matches_count}[/cyan] Eventos")
        if stats_parts:
            console.print("  " + "  |  ".join(stats_parts) + "\n")

        description = _strip_html(club.description)
        if description:
            for line in description.splitlines():
                wrapped = textwrap.fill(line, width=_WIDTH) if line else ""
                console.print(wrapped)


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
@_timed
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

    Activity reflects general Chess.com usage, not club tournament
    participation.  Tiers: 'This week' (active on Chess.com in the past
    7 days), 'This month' (past 30 days), or 'Inactive' (longer).

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
            activity_label = _ACTIVITY_LABEL.get(
                m.activity or "", m.activity or "—"
            )
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
@_timed
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
    games: str | None = typer.Option(
        None,
        "--games",
        "-g",
        help=(
            "Show games for a tournament. "
            "Accepts the # from the list, a partial name, or an exact ID."
        ),
    ),
):
    """List tournaments organised by the club.

    Use --games to show all games for a specific tournament.  Pass the #
    shown in the list, a partial name, or the exact tournament ID.

    Use --details to show per-player standings for each tournament.
    """
    try:
        service = _get_service()
        data = service.get_club_tournaments(slug)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    # ------------------------------------------------------------------
    # --games branch: resolve tournament and show its games
    # ------------------------------------------------------------------
    if games is not None:
        data.sort(key=lambda t: t.end_date or 0, reverse=False)

        tournament = None
        if games.strip().isdigit():
            idx = int(games.strip())
            if 1 <= idx <= len(data):
                tournament = data[idx - 1]

        if tournament is None:
            matches = service.find_tournaments_by_name_or_id(slug, games)
            if not matches:
                console.print(
                    f"[red]Error:[/red] No tournament matching "
                    f"[bold]{games!r}[/bold].",
                    highlight=False,
                )
                raise typer.Exit(1)
            if len(matches) > 1:
                console.print(
                    f"[yellow]Note:[/yellow] {len(matches)} tournaments "
                    f"matched. Using the most recent: "
                    f"[bold]{matches[0].name}[/bold]."
                )
            tournament = matches[0]

        console.print(
            f"[dim]Tournament: {tournament.name} "
            f"(ID: {tournament.id}, "
            f"{_fmt_date(tournament.start_date)}–"
            f"{_fmt_date(tournament.end_date)})[/dim]"
        )

        try:
            with console.status("[dim]Fetching games…[/dim]", spinner="dots"):
                t_results = service.get_tournament_results(
                    tournament.id,
                    tournament_type=tournament.tournament_type,
                    tournament_url=tournament.url,
                )
                game_data = service.get_tournament_games(
                    tournament, results=t_results
                )
        except AuthenticationRequiredError as e:
            console.print(f"[red]Error:[/red] {e}", highlight=False)
            raise typer.Exit(1)

        participant_count = len({r.player for r in t_results})
        with_accuracy = sum(1 for g in game_data if g.avg_accuracy is not None)

        if output == OutputFormat.json:
            rows = []
            for g in game_data:
                d = asdict(g)
                d["avg_accuracy"] = g.avg_accuracy
                rows.append(d)
            print(json.dumps(rows, indent=2))

        elif output == OutputFormat.csv:
            _gfields = [
                "white",
                "black",
                "result",
                "opening_eco",
                "played_at",
                "white_accuracy",
                "black_accuracy",
                "avg_accuracy",
                "url",
            ]
            rows = []
            for g in game_data:
                d = asdict(g)
                d["avg_accuracy"] = g.avg_accuracy
                rows.append(d)
            print(_to_csv(rows, _gfields), end="")

        else:
            gtable = Table(title=tournament.name, show_lines=False)
            gtable.add_column("White", style="cyan")
            gtable.add_column("W%", justify="right")
            gtable.add_column("Black", style="cyan")
            gtable.add_column("B%", justify="right")
            gtable.add_column("Avg%", justify="right", style="bold")
            gtable.add_column("Result", justify="center")
            gtable.add_column("Date", justify="right")
            gtable.add_column("Link", no_wrap=True)

            for g in game_data:
                link = f"[link={g.url}]view[/link]" if g.url else "—"
                gtable.add_row(
                    g.white,
                    _fmt_acc(g.white_accuracy),
                    g.black,
                    _fmt_acc(g.black_accuracy),
                    _fmt_acc(g.avg_accuracy),
                    g.result,
                    _fmt_date(g.played_at),
                    link,
                )

            console.print(gtable)
            using_member_fallback = (
                participant_count == 0 and len(game_data) > 0
            )
            participants_label = (
                "club members (leaderboard unavailable)"
                if using_member_fallback
                else f"{participant_count} participants"
            )
            console.print(
                f"[dim]Total: {len(game_data)} games "
                f"({with_accuracy} with accuracy data, "
                f"{participants_label})[/]"
            )
            if not game_data:
                if participant_count == 0:
                    console.print(
                        "[yellow]Tip:[/yellow] Leaderboard returned 0 "
                        "participants and no club members could be fetched. "
                        "Check credentials "
                        "([bold]chessclub auth setup[/bold])."
                    )
                else:
                    console.print(
                        f"[yellow]Tip:[/yellow] {participant_count} "
                        "participants found but no games matched the "
                        "tournament time window. "
                        "This is a known Chess.com API issue."
                    )
        return

    # ------------------------------------------------------------------
    # Default: list tournaments
    # ------------------------------------------------------------------
    if output == OutputFormat.json:
        rows = [asdict(t) for t in data]
        if details:
            for row, t in zip(rows, data, strict=True):
                try:
                    results = service.get_tournament_results(
                        t.id,
                        tournament_type=t.tournament_type,
                        tournament_url=t.url,
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
        data.sort(key=lambda t: t.end_date or 0, reverse=False)

        table = Table(title=f"Tournaments — {slug}", show_lines=False)
        table.add_column("#", justify="right", style="dim", width=4)
        table.add_column("Name", style="cyan", no_wrap=False)
        table.add_column("Type", style="dim")
        table.add_column("Date", justify="right")
        table.add_column("Players", justify="right")
        table.add_column("Winner pts", justify="right")

        for i, t in enumerate(data, 1):
            score = str(t.winner_score) if t.winner_score is not None else "—"
            table.add_row(
                str(i),
                t.name.lstrip(),
                t.tournament_type,
                _fmt_date(t.start_date),
                str(t.player_count),
                score,
            )

        console.print(table)
        console.print(
            f"[dim]Total: {len(data)} tournaments — "
            "use [bold]--games <#>[/bold] to view games[/]"
        )

        if details:
            for t in data:
                console.rule(f"[bold]{t.name}[/bold]")
                try:
                    results = service.get_tournament_results(
                        t.id,
                        tournament_type=t.tournament_type,
                        tournament_url=t.url,
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


@club_app.command()
@_timed
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
            # Build tournament ID → name map for display (cached, no cost)
            tournaments = service.get_club_tournaments(slug)
            tid_to_name = {t.id: t.name for t in tournaments}
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    if min_accuracy > 0:
        data = [
            g
            for g in data
            if g.avg_accuracy is not None and g.avg_accuracy >= min_accuracy
        ]

    with_accuracy = sum(1 for g in data if g.avg_accuracy is not None)

    def _fmt_acc(val: float | None) -> str:
        """Format an accuracy value as a 1-decimal string."""
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
        table = Table(title=f"Tournament Games — {slug}", show_lines=False)
        table.add_column("Tournament", style="dim", no_wrap=True, max_width=20)
        table.add_column("White", style="cyan")
        table.add_column("W%", justify="right")
        table.add_column("Black", style="cyan")
        table.add_column("B%", justify="right")
        table.add_column("Avg%", justify="right", style="bold")
        table.add_column("Result", justify="center")
        table.add_column("Date", justify="right")

        for g in data:
            t_label = tid_to_name.get(
                g.tournament_id or "", g.tournament_id or "—"
            )
            table.add_row(
                t_label,
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
            scope_hint = f"last {last_n}" if n else "all"
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


# ---------------------------------------------------------------------------
# leaderboard command
# ---------------------------------------------------------------------------


@club_app.command()
@_timed
def leaderboard(
    slug: str,
    year: int | None = typer.Option(
        None,
        "--year",
        "-y",
        help="Calendar year.  Omit for an all-time leaderboard.",
    ),
    month: int | None = typer.Option(
        None,
        "--month",
        "-m",
        min=1,
        max=12,
        help="Month (1–12).  Omit for a full-year leaderboard.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
) -> None:
    """Show the club leaderboard for a year, month, or all time.

    Aggregates tournament results and ranks players by total chess
    score.  Omit --year for an all-time leaderboard.  Requires
    authentication.

    Examples:

        chessclub club leaderboard my-club

        chessclub club leaderboard my-club --year 2025

        chessclub club leaderboard my-club --year 2025 --month 3
    """
    from chessclub.services.leaderboard_service import LeaderboardService

    try:
        service = _get_service()
        lb = LeaderboardService(service.provider)
        if year and month:
            period_label = f"{year}/{month:02d}"
        elif year:
            period_label = str(year)
        else:
            period_label = "All time"
        with console.status(
            f"[dim]Fetching leaderboard for {period_label}…[/dim]",
            spinner="dots",
        ):
            data = lb.get_leaderboard(slug, year=year, month=month)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    if not data:
        console.print(
            f"[yellow]No tournament data found for {period_label}.[/yellow]"
        )
        raise typer.Exit(0)

    if output == OutputFormat.json:
        print(json.dumps([asdict(p) for p in data], indent=2))

    elif output == OutputFormat.csv:
        _fields = [
            "username",
            "tournaments_played",
            "wins",
            "total_score",
            "avg_score",
        ]
        print(_to_csv([asdict(p) for p in data], _fields), end="")

    else:
        table = Table(
            title=f"Leaderboard {period_label} — {slug}",
            show_lines=False,
        )
        table.add_column("#", justify="right", style="dim", width=4)
        table.add_column("Player", style="cyan")
        table.add_column("Tournaments", justify="right")
        table.add_column("Wins", justify="right")
        table.add_column("Total pts", justify="right", style="bold")
        table.add_column("Avg pts", justify="right")

        for i, p in enumerate(data, 1):
            table.add_row(
                str(i),
                p.username,
                str(p.tournaments_played),
                str(p.wins),
                f"{p.total_score:.1f}",
                f"{p.avg_score:.1f}",
            )

        console.print(table)
        console.print(f"[dim]{len(data)} players · {period_label}[/dim]")


# ---------------------------------------------------------------------------
# matchups command
# ---------------------------------------------------------------------------


@club_app.command()
@_timed
def matchups(
    slug: str,
    last_n: int = typer.Option(
        5,
        "--last-n",
        help=(
            "Scan only the N most recent tournaments. "
            "Use 0 to scan all tournaments."
        ),
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
) -> None:
    """Show head-to-head records between club members.

    Fetches games from the last N tournaments and tallies
    win/loss/draw results for every pair of players who have
    faced each other.  Requires authentication.

    Examples:

        chessclub club matchups my-club

        chessclub club matchups my-club --last-n 10

        chessclub club matchups my-club --last-n 0  # all
    """
    from chessclub.services.matchup_service import MatchupService

    try:
        service = _get_service()
        ms = MatchupService(service.provider)
        n = last_n if last_n > 0 else None
        scope = f"last {last_n}" if n else "all"
        with console.status(
            f"[dim]Fetching matchups ({scope} tournaments)…[/dim]",
            spinner="dots",
        ):
            data = ms.get_matchups(slug, last_n=n)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    if not data:
        console.print("[yellow]No matchup data found.[/yellow]")
        raise typer.Exit(0)

    if output == OutputFormat.json:
        print(json.dumps([asdict(m) for m in data], indent=2))

    elif output == OutputFormat.csv:
        _fields = [
            "player_a",
            "player_b",
            "wins_a",
            "wins_b",
            "draws",
            "total_games",
            "last_played",
        ]
        print(_to_csv([asdict(m) for m in data], _fields), end="")

    else:
        table = Table(
            title=f"Head-to-Head — {slug}",
            show_lines=False,
        )
        table.add_column("Player A", style="cyan")
        table.add_column("W", justify="right")
        table.add_column("D", justify="right", style="dim")
        table.add_column("W", justify="right")
        table.add_column("Player B", style="cyan")
        table.add_column("Total", justify="right", style="bold")

        for m in data:
            table.add_row(
                m.player_a,
                str(m.wins_a),
                str(m.draws),
                str(m.wins_b),
                m.player_b,
                str(m.total_games),
            )

        console.print(table)
        console.print(f"[dim]{len(data)} matchups · {scope} tournaments[/dim]")


# ---------------------------------------------------------------------------
# attendance command
# ---------------------------------------------------------------------------


@club_app.command()
@_timed
def attendance(
    slug: str,
    last_n: int = typer.Option(
        0,
        "--last-n",
        help=(
            "Only consider the N most recent tournaments. 0 = all tournaments."
        ),
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
) -> None:
    """Rank players by tournament attendance and consistency.

    Shows how many tournaments each player participated in, their
    attendance percentage, and current / longest consecutive streaks.
    Requires authentication.

    Examples:

        chessclub club attendance my-club

        chessclub club attendance my-club --last-n 20
    """
    from chessclub.services.attendance_service import AttendanceService

    try:
        service = _get_service()
        att = AttendanceService(service.provider)
        n: int | None = last_n if last_n > 0 else None
        scope = f"last {last_n}" if n else "all"
        with console.status(
            f"[dim]Fetching attendance ({scope} tournaments)…[/dim]",
            spinner="dots",
        ):
            data = att.get_attendance(slug, last_n=n)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    if not data:
        console.print("[yellow]No attendance data found.[/yellow]")
        raise typer.Exit(0)

    if output == OutputFormat.json:
        print(json.dumps([asdict(a) for a in data], indent=2))

    elif output == OutputFormat.csv:
        _fields = [
            "username",
            "tournaments_played",
            "total_tournaments",
            "participation_pct",
            "current_streak",
            "max_streak",
        ]
        print(_to_csv([asdict(a) for a in data], _fields), end="")

    else:
        total_t = data[0].total_tournaments if data else 0
        table = Table(
            title=f"Attendance — {slug} ({total_t} tournaments)",
            show_lines=False,
        )
        table.add_column("#", justify="right", style="dim", width=4)
        table.add_column("Player", style="cyan")
        table.add_column("Played", justify="right")
        table.add_column("%", justify="right", style="bold")
        table.add_column("Streak", justify="right")
        table.add_column("Best", justify="right")

        for i, a in enumerate(data, 1):
            table.add_row(
                str(i),
                a.username,
                str(a.tournaments_played),
                f"{a.participation_pct:.0f}%",
                str(a.current_streak),
                str(a.max_streak),
            )

        console.print(table)
        console.print(f"[dim]{len(data)} players · {scope} tournaments[/dim]")


# ---------------------------------------------------------------------------
# records command
# ---------------------------------------------------------------------------


@club_app.command()
@_timed
def records(
    slug: str,
    last_n: int = typer.Option(
        5,
        "--last-n",
        help=(
            "Tournaments to scan for game-based records "
            "(accuracy).  0 = all.  Tournament-based records "
            "always scan every tournament."
        ),
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
) -> None:
    """Show notable club records and highlights.

    Identifies the highest tournament score, most active player,
    biggest tournament, best accuracy, and more.  Game-based records
    (accuracy) scan only the last N tournaments by default.
    Requires authentication.

    Examples:

        chessclub club records my-club

        chessclub club records my-club --last-n 0
    """
    from chessclub.services.records_service import RecordsService

    try:
        service = _get_service()
        rs = RecordsService(service.provider)
        n: int | None = last_n if last_n > 0 else None
        scope = f"last {last_n}" if n else "all"
        with console.status(
            f"[dim]Fetching records ({scope} tournaments for games)…[/dim]",
            spinner="dots",
        ):
            data = rs.get_records(slug, last_n=n)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    if not data:
        console.print("[yellow]No records found.[/yellow]")
        raise typer.Exit(0)

    if output == OutputFormat.json:
        print(json.dumps([asdict(r) for r in data], indent=2))

    elif output == OutputFormat.csv:
        _fields = ["category", "value", "player", "detail", "date"]
        print(_to_csv([asdict(r) for r in data], _fields), end="")

    else:
        table = Table(
            title=f"Club Records — {slug}",
            show_lines=True,
        )
        table.add_column("Record", style="bold")
        table.add_column("Value", justify="right", style="cyan")
        table.add_column("Player")
        table.add_column("Detail", style="dim")
        table.add_column("Date", justify="right")

        for r in data:
            table.add_row(
                r.category,
                r.value,
                r.player or "—",
                r.detail or "",
                _fmt_date(r.date),
            )

        console.print(table)
        console.print(f"[dim]{len(data)} records[/dim]")


# ---------------------------------------------------------------------------
# player commands
# ---------------------------------------------------------------------------


@player_app.command(name="rating-history")
@_timed
def rating_history(
    username: str,
    club: str = typer.Option(
        ...,
        "--club",
        "-c",
        help="Club slug to scope the history to.",
    ),
    last_n: int | None = typer.Option(
        None,
        "--last-n",
        help=(
            "Only scan the N most recent tournaments. "
            "Omit to scan all tournaments."
        ),
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
) -> None:
    """Show a player's rating evolution across club tournaments.

    For each tournament the player participated in, displays
    their rating, finishing position, and score.  Requires
    authentication.

    Examples:

        chessclub player rating-history joaosilva -c my-club

        chessclub player rating-history joaosilva -c my-club --last-n 10
    """
    from chessclub.services.rating_history_service import (
        RatingHistoryService,
    )

    try:
        service = _get_service()
        rhs = RatingHistoryService(service.provider)
        scope = f"last {last_n}" if last_n else "all"
        with console.status(
            f"[dim]Fetching rating history for {username} "
            f"({scope} tournaments)…[/dim]",
            spinner="dots",
        ):
            data = rhs.get_rating_history(club, username, last_n=last_n)
    except AuthenticationRequiredError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    if not data:
        console.print(
            f"[yellow]No tournament data found for "
            f"{username} in {club}.[/yellow]"
        )
        raise typer.Exit(0)

    if output == OutputFormat.json:
        print(json.dumps([asdict(s) for s in data], indent=2))

    elif output == OutputFormat.csv:
        _fields = [
            "tournament_id",
            "tournament_name",
            "tournament_type",
            "tournament_date",
            "rating",
            "position",
            "score",
        ]
        print(_to_csv([asdict(s) for s in data], _fields), end="")

    else:
        table = Table(
            title=f"Rating History — {username} @ {club}",
            show_lines=False,
        )
        table.add_column("#", justify="right", style="dim", width=4)
        table.add_column("Tournament")
        table.add_column("Type", style="dim")
        table.add_column("Date", justify="right")
        table.add_column("Rating", justify="right", style="bold")
        table.add_column("Pos", justify="right")
        table.add_column("Score", justify="right")

        for i, s in enumerate(data, 1):
            table.add_row(
                str(i),
                s.tournament_name,
                s.tournament_type,
                _fmt_date(s.tournament_date),
                str(s.rating) if s.rating else "—",
                str(s.position),
                f"{s.score:.1f}" if s.score is not None else "—",
            )

        console.print(table)
        console.print(f"[dim]{len(data)} tournaments · {username}[/dim]")


# ---------------------------------------------------------------------------
# cache commands
# ---------------------------------------------------------------------------


@cache_app.command(name="stats")
@_timed
def cache_stats() -> None:
    """Show cache statistics (entry count and database size)."""
    from chessclub.providers.chesscom.cache import SQLiteCache

    cache = SQLiteCache()
    s = cache.stats()
    if not s:
        console.print("[yellow]Cache not found or unreadable.[/yellow]")
        raise typer.Exit(1)
    n = s["total"]
    console.print(
        f"Entries : {n} total  ({s['active']} active, {s['expired']} expired)"
    )
    console.print(f"Location: {SQLiteCache._DB_PATH}")
    console.print(f"Size    : {s['size_bytes'] / 1024:.1f} KB")


@cache_app.command(name="clear")
@_timed
def cache_clear(
    expired_only: bool = typer.Option(
        False,
        "--expired",
        help="Remove only expired entries, keeping valid cached responses.",
    ),
) -> None:
    """Clear cached API responses.

    By default removes all entries.  Use --expired to remove only entries
    whose TTL has elapsed while keeping still-valid responses in place.
    """
    from chessclub.providers.chesscom.cache import SQLiteCache

    cache = SQLiteCache()
    if expired_only:
        n = cache.purge_expired()
        label = "entry" if n == 1 else "entries"
        console.print(f"Removed {n} expired {label}.")
    else:
        n = cache.clear()
        label = "entry" if n == 1 else "entries"
        console.print(f"Cache cleared ({n} {label} removed).")
