import typer
from chessclub.providers.chesscom.client import ChessComClient
from chessclub.services.club_service import ClubService

app = typer.Typer()

@app.command()
def club_info(slug: str):
    provider = ChessComClient(
        user_agent="Chessclub/0.1 (contato: seu-email@exemplo.com)"
    )

    service = ClubService(provider)
    print(service.get_club_name(slug))