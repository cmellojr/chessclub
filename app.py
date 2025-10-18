from chessdotcom import Client, get_leaderboards
from flask import Flask, jsonify
import requests
import json

Client.request_config = {
    "headers": {
        "User-Agent": "ChessClubStats/1.0 (contato: seu@email.com)"
    },
    # opcional: timeout, retries etc.
    # "timeout": 20,
}
app = Flask(__name__)

CHESS_API_BASE = "https://api.chess.com/pub/club"

username = "magnuscarlsen"  # Replace with the desired username
url = f"https://api.chess.com/pub/player/{username}"

response = requests.get(url)

if response.status_code == 200:
    player_data = json.loads(response.text)
    print(player_data)
else:
    print(f"Error: {response.status_code}")


# Função auxiliar para requisições GET
def fetch_data(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to fetch data. Status code: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# Rota: Informações básicas do clube
@app.route('/clube/<club_name>', methods=['GET'])
def get_club_info(club_name):
    url = f"{CHESS_API_BASE}/{club_name}"
    data = fetch_data(url)
    return jsonify(data)


# Rota: Membros do clube
@app.route('/clube/<club_name>/membros', methods=['GET'])
def get_club_members(club_name):
    url = f"{CHESS_API_BASE}/{club_name}/members"
    data = fetch_data(url)
    return jsonify(data)


# Rota: Torneios do clube
@app.route('/clube/<club_name>/torneios', methods=['GET'])
def get_club_tournaments(club_name):
    url = f"{CHESS_API_BASE}/{club_name}/tournaments"
    data = fetch_data(url)
    return jsonify(data)


# Rota: Melhores jogadores dos torneios (exemplo simplificado)
@app.route('/clube/<club_name>/melhores-jogadores', methods=['GET'])
def get_top_players(club_name):
    tournaments_url = f"{CHESS_API_BASE}/{club_name}/tournaments"
    tournaments = fetch_data(tournaments_url)
    
    top_players = []

    if "error" in tournaments:
        return jsonify({"error": "Erro ao buscar torneios do clube."})

    for tournament in tournaments.get('finished', [])[:3]:  # Pegando só os últimos 3 torneios
        tour_url = tournament.get('url')
        if not tour_url:
            continue

        tour_id = tour_url.split('/')[-1]
        tour_api_url = f"https://api.chess.com/pub/tournament/{tour_id}"
        tour_data = fetch_data(tour_api_url)

        if "error" in tour_data:
            continue

        players = []
        if 'players' in tour_data:
            for player in tour_data['players']:
                username = player.get('username')
                points = player.get('points', 0)
                players.append({'username': username, 'points': points})

            sorted_players = sorted(players, key=lambda x: x['points'], reverse=True)
            top_players.append({
                'tournament': tournament.get('name'),
                'top_players': sorted_players[:3]  # Top 3 jogadores
            })

    return jsonify(top_players)


if __name__ == '__main__':
    app.run(debug=True)
