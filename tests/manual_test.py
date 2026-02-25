from chessclub.providers.chesscom import ChessComProvider

provider = ChessComProvider(
    user_agent="Chessclub/0.1 (contact: cmellojr@gmail.com)"
)

club = provider.get_club("clube-de-xadrez-de-jundiai")
print(club)

members = provider.get_club_members("clube-de-xadrez-de-jundiai")
print(f"Members: {len(members)}")
