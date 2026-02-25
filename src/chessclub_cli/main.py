import os
import webbrowser
import typer
from datetime import datetime
from rich.console import Console
from rich.table import Table
from chessclub.auth import credentials as creds_store
from chessclub.providers.chesscom.client import ChessComClient
from chessclub.services.club_service import ClubService

app = typer.Typer()
club_app = typer.Typer()
auth_app = typer.Typer(help="Gerenciar autenticação com o Chess.com.")

app.add_typer(club_app, name="club")
app.add_typer(auth_app, name="auth")

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_credentials() -> tuple[str | None, str | None]:
    """Env vars têm prioridade; depois lê do arquivo de configuração."""
    access_token = os.getenv("CHESSCOM_ACCESS_TOKEN")
    phpsessid = os.getenv("CHESSCOM_PHPSESSID")
    if access_token and phpsessid:
        return access_token, phpsessid
    stored = creds_store.load()
    return stored.get("access_token"), stored.get("phpsessid")


def _get_service() -> ClubService:
    access_token, phpsessid = _load_credentials()
    provider = ChessComClient(
        user_agent="Chessclub/0.1 (contato: cmellojr@gmail.com)",
        access_token=access_token,
        phpsessid=phpsessid,
    )
    return ClubService(provider)


# ---------------------------------------------------------------------------
# auth commands
# ---------------------------------------------------------------------------

@auth_app.command()
def setup():
    """Configura as credenciais do Chess.com e salva localmente."""
    console.print("\n[bold]Configuração de credenciais do Chess.com[/bold]\n")
    console.print("Vamos abrir o Chess.com no seu browser. Faça login normalmente e siga as instruções abaixo.\n")

    typer.confirm("Pressione Enter para abrir o browser", default=True, prompt_suffix=" ")
    webbrowser.open("https://www.chess.com/login")

    console.print("\n[bold]Como obter os cookies após o login:[/bold]")
    console.print("  1. Com o Chess.com aberto, pressione [cyan]F12[/cyan] para abrir o DevTools")
    console.print("  2. Vá para a aba [cyan]Application[/cyan] (Chrome) ou [cyan]Storage[/cyan] (Firefox)")
    console.print("  3. No menu lateral, clique em [cyan]Cookies → https://www.chess.com[/cyan]")
    console.print("  4. Copie o valor de [cyan]ACCESS_TOKEN[/cyan] e [cyan]PHPSESSID[/cyan]\n")

    access_token = typer.prompt("Cole o valor de ACCESS_TOKEN", hide_input=True)
    phpsessid = typer.prompt("Cole o valor de PHPSESSID", hide_input=True)

    console.print("\n[dim]Validando credenciais...[/dim]")
    try:
        client = ChessComClient(
            user_agent="Chessclub/0.1 (contato: cmellojr@gmail.com)",
            access_token=access_token,
            phpsessid=phpsessid,
        )
        client.get_club("chess-com-developer-community")
    except Exception as e:
        console.print(f"[red]Erro ao validar credenciais:[/red] {e}")
        raise typer.Exit(1)

    creds_store.save(access_token, phpsessid)
    console.print(f"[green]✓ Credenciais salvas em:[/green] {creds_store.credentials_path()}")
    console.print("[dim]O ACCESS_TOKEN expira em ~24h. Rode [bold]chessclub auth setup[/bold] novamente quando necessário.[/dim]\n")


@auth_app.command()
def status():
    """Exibe o status das credenciais configuradas."""
    access_token, phpsessid = _load_credentials()

    if not access_token or not phpsessid:
        console.print("[yellow]Nenhuma credencial configurada.[/yellow]")
        console.print("Execute [bold]chessclub auth setup[/bold] para configurar.")
        raise typer.Exit(1)

    source = "variáveis de ambiente" if os.getenv("CHESSCOM_ACCESS_TOKEN") else creds_store.credentials_path()
    console.print(f"[green]✓ Credenciais encontradas[/green] ({source})")

    console.print("[dim]Validando com o Chess.com...[/dim]")
    try:
        client = ChessComClient(
            user_agent="Chessclub/0.1 (contato: cmellojr@gmail.com)",
            access_token=access_token,
            phpsessid=phpsessid,
        )
        client.get_club("chess-com-developer-community")
        console.print("[green]✓ Credenciais válidas.[/green]")
    except PermissionError:
        console.print("[red]✗ Credenciais expiradas ou inválidas.[/red]")
        console.print("Execute [bold]chessclub auth setup[/bold] para renovar.")
        raise typer.Exit(1)


@auth_app.command()
def clear():
    """Remove as credenciais salvas localmente."""
    removed = creds_store.clear()
    if removed:
        console.print("[green]✓ Credenciais removidas.[/green]")
    else:
        console.print("[yellow]Nenhuma credencial salva encontrada.[/yellow]")


# ---------------------------------------------------------------------------
# club commands
# ---------------------------------------------------------------------------

@club_app.command()
def stats(slug: str):
    """Exibe o nome do clube."""
    service = _get_service()
    print(service.get_club_name(slug))


@club_app.command()
def members(slug: str):
    """Lista os membros do clube."""
    service = _get_service()
    data = service.get_club_members(slug)

    table = Table(title=f"Membros — {slug}")
    table.add_column("Username", style="cyan")
    for m in data:
        table.add_row(m.get("username", ""))

    console.print(table)


@club_app.command()
def tournaments(slug: str):
    """Lista os torneios organizados pelo clube."""
    def fmt_date(ts) -> str:
        if not ts:
            return "—"
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")

    try:
        service = _get_service()
        data = service.get_club_tournaments(slug)
    except PermissionError as e:
        console.print(f"[red]Erro:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    table = Table(title=f"Torneios — {slug}", show_lines=False)
    table.add_column("Nome", style="cyan", no_wrap=False)
    table.add_column("Tipo", style="dim")
    table.add_column("Data", justify="right")
    table.add_column("Jogadores", justify="right")
    table.add_column("Pts vencedor", justify="right")

    for t in data:
        winner = t.get("winner") or {}
        score = str(winner.get("score", "—")) if winner else "—"
        table.add_row(
            t.get("name", ""),
            t.get("tournament_type", ""),
            fmt_date(t.get("start_time")),
            str(t.get("registered_user_count", 0)),
            score,
        )

    console.print(table)
    console.print(f"[dim]Total: {len(data)} torneios[/]")
