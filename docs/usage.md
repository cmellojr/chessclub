# chessclub — Guia de Uso

Este guia cobre instalação, autenticação e todos os comandos da CLI com
exemplos de saída reais.

---

## Instalação

```bash
git clone https://github.com/your-org/chessclub.git
cd chessclub
pip install -e .
```

Verifique:

```
$ chessclub --help

 Usage: chessclub [OPTIONS] COMMAND [ARGS]...

╭─ Options ──────────────────────────────────────────────────╮
│ --help   Show this message and exit.                       │
╰────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────╮
│ auth   Manage Chess.com authentication.                    │
│ club   Club-related commands.                              │
╰────────────────────────────────────────────────────────────╯
```

---

## Autenticação

A maioria dos comandos requer credenciais Chess.com. Há dois métodos.

### Método 1 — Cookies (padrão)

**Pré-requisito:** extensão `chessclub Cookie Helper` instalada no Chrome
(carregar sem empacotar a partir de `tools/chessclub-cookie-helper/`).

```
$ chessclub auth setup

Abrindo https://www.chess.com no navegador...
Faça login e clique no ícone da extensão na barra do navegador.

Paste ACCESS_TOKEN: ****
Paste PHPSESSID   : ****

✓ Credenciais salvas em ~/.config/chessclub/credentials.json
```

### Método 2 — OAuth 2.0 (quando disponível)

```
$ chessclub auth login
```

Abre o navegador, completa o fluxo PKCE e salva tokens em
`~/.config/chessclub/oauth_token.json`. Tokens se renovam automaticamente.

### Status das credenciais

```
$ chessclub auth status

OAuth token  : não configurado
Cookie auth  : ✓ ativo
  ACCESS_TOKEN : ****...abcd
  PHPSESSID    : ****...ef12
```

### Limpar credenciais

```
$ chessclub auth clear
Credenciais removidas.
```

---

## Comandos de Clube

Todos os comandos de clube aceitam `--output json` ou `--output csv` para
integração com outras ferramentas.

### `chessclub club stats <slug>`

Exibe informações gerais do clube: nome, membros, data de criação, eventos
realizados e descrição.

```
$ chessclub club stats clube-de-xadrez-de-jundiai

╭──────────────────────────────────────────────────────────────────────────────╮
│                    🇧🇷 Clube de Xadrez de Jundiaí                           │
╰──────────────────────────────────────────────────────────────────────────────╯
  752 Membros  |  Criado em 15/02/2022  |  141 Eventos

Bem-vindo(a) ao Clube de Xadrez de Jundiaí! Somos um clube tradicional
localizado em Jundiaí, SP. Promovemos torneios mensais, aulas e eventos
para jogadores de todos os níveis.
```

> **Nota:** "Eventos" requer autenticação (conta os torneios internos).
> Sem credenciais, a linha aparece sem o campo de eventos.

**Saída JSON:**

```
$ chessclub club stats clube-de-xadrez-de-jundiai --output json

{
  "id": "clube-de-xadrez-de-jundiai",
  "provider_id": "352057",
  "name": "Clube de Xadrez de Jundiaí",
  "description": "<p>Bem-vindo(a)...</p>",
  "country": "https://api.chess.com/pub/country/BR",
  "url": "https://www.chess.com/club/clube-de-xadrez-de-jundiai",
  "members_count": 752,
  "created_at": 1644940255,
  "location": "Rua São Jorge, 28 - 1o andar - Jundiaí - SP",
  "matches_count": 141
}
```

---

### `chessclub club members <slug>`

Lista todos os membros do clube com tier de atividade e data de entrada.

```
$ chessclub club members clube-de-xadrez-de-jundiai

               Members — clube-de-xadrez-de-jundiai
 Username           Activity      Joined
 ─────────────────────────────────────────────────
 joaosilva          This week     2022-03-01
 mariaoliveira      This week     2022-05-14
 carlosmendes       This month    2023-01-20
 anapaula           Inactive      2022-02-20
 ...
 Total: 752 members
```

**Com títulos** (uma chamada de API por membro — lento para clubes grandes):

```
$ chessclub club members clube-de-xadrez-de-jundiai --details

 Username           Title   Activity      Joined
 ──────────────────────────────────────────────────────
 joaosilva          FM      This week     2022-03-01
 mariaoliveira      —       This week     2022-05-14
 ...
```

**Saída CSV:**

```
$ chessclub club members clube-de-xadrez-de-jundiai --output csv

username,title,activity,joined_at
joaosilva,,weekly,1646092800
mariaoliveira,,weekly,1652486400
carlosmendes,,monthly,1674172800
```

---

### `chessclub club tournaments <slug>`

Lista os torneios organizados pelo clube, numerados do mais antigo (#1)
ao mais recente (#N). Requer autenticação.

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai

                Tournaments — clube-de-xadrez-de-jundiai
  #    Name                                    Type    Date         Players
 ────────────────────────────────────────────────────────────────────────────
   1   1o Torneio XIII de Agosto               swiss   2022-03-05        12
   2   2o Torneio XIII de Agosto               swiss   2022-04-02        15
   3   1o Arena de Abertura                    arena   2022-04-16        24
  ...
 140   25o Torneio XIII de Agosto              swiss   2026-01-05        22
 141   26o Torneio XIII de Agosto              swiss   2026-02-01        24

 Total: 141 tournaments — use --games <#> to view games
```

**Com standings de cada torneio:**

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --details

  #    Name                         ...
 ─────────────────────────────────────
 ...

 ──────────── 26o Torneio XIII de Agosto ────────────
  #   Player           Score   Rating
  1   joaosilva        8.0     1850
  2   mariaoliveira    7.0     1740
  3   carlosmendes     6.5     1620
  ...
```

**Saída JSON:**

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --output json

[
  {
    "id": "6100001",
    "name": "1o Torneio XIII de Agosto",
    "tournament_type": "swiss",
    "status": "finished",
    "start_date": 1646438400,
    "end_date": 1646524800,
    "player_count": 12,
    "winner_username": "joaosilva",
    "winner_score": 9.0,
    "club_slug": "clube-de-xadrez-de-jundiai"
  },
  ...
]
```

---

### `chessclub club tournaments <slug> --games <ref>`

Exibe os jogos de um torneio específico, rankeados por acurácia Stockfish.
`<ref>` pode ser o `#` da listagem, um nome parcial ou o ID exato.

**Por número:**

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --games 141

Tournament: 26o Torneio XIII de Agosto (ID: 6265185, 2026-02-01–2026-02-28)

          26o Torneio XIII de Agosto
 White            W%     Black            B%    Avg%   Result   Date         Link
 ─────────────────────────────────────────────────────────────────────────────────
 joaosilva        94.5   mariaoliveira    89.2   91.9   1-0      2026-02-03   view
 carlosmendes     87.1   anapaula         85.4   86.3   0-1      2026-02-03   view
 joaosilva        91.2   carlosmendes     78.6   84.9   1-0      2026-02-10   view
 ...

 Total: 47 games (32 with accuracy data, 24 participants)
```

> **Link:** em terminais compatíveis (Windows Terminal, iTerm2), a coluna
> `view` é um hyperlink clicável que abre a partida no Chess.com.

**Por nome parcial:**

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --games "Fevereiro"

Note: 3 tournaments matched. Using the most recent: 26o Torneio...
Tournament: ...
```

**Por ID exato:**

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --games 6265185
```

**Saída CSV** (inclui URL da partida):

```
$ chessclub club tournaments clube-de-xadrez-de-jundiai --games 141 --output csv

white,black,result,opening_eco,played_at,white_accuracy,black_accuracy,avg_accuracy,url
joaosilva,mariaoliveira,1-0,E20,1738540800,94.5,89.2,91.85,https://www.chess.com/game/live/...
...
```

---

### `chessclub club games <slug>`

Agrega os jogos dos últimos N torneios do clube, rankeados por acurácia.
Útil para identificar as partidas de melhor qualidade do clube.

```
$ chessclub club games clube-de-xadrez-de-jundiai

 White            W%     Black            B%    Avg%   Result   Date
 ─────────────────────────────────────────────────────────────────────
 joaosilva        97.2   mariaoliveira    94.1   95.7   1-0      2026-02-10
 carlosmendes     93.8   joaosilva        92.5   93.2   0-1      2026-01-25
 ...

 Total: 231 games (189 with accuracy data)
```

**Variar a janela de torneios:**

```bash
# Últimos 10 torneios (padrão: 5)
chessclub club games clube-de-xadrez-de-jundiai --last-n 10

# Todos os torneios (pode ser muito lento)
chessclub club games clube-de-xadrez-de-jundiai --last-n 0
```

---

## Cache em disco

Respostas de API são armazenadas em `~/.cache/chessclub/` para evitar
chamadas repetidas. Os TTLs atuais são:

| Endpoint | TTL | Justificativa |
|---|---|---|
| Arquivos de jogos — mês passado | **30 dias** | Histórico imutável |
| Arquivos de jogos — mês atual | **1 hora** | Rodadas ocorrem em horas |
| Perfil do jogador | **24 horas** | Rating atualizado no máximo 1×/dia |
| Lista de membros do clube | **1 hora** | Entradas/saídas são raras |
| Info do clube | **24 horas** | Nome/descrição quase nunca muda |
| Leaderboard de torneio | **7 dias** | Torneio encerrado é imutável |
| Lista de torneios do clube | **30 minutos** | Novos torneios aparecem semanalmente |

**Limpar o cache:**

```bash
rm -rf ~/.cache/chessclub/
```

---

## Uso como biblioteca Python

O `chessclub` pode ser usado diretamente como pacote Python, sem a CLI.

### Setup mínimo

```python
from chessclub.providers.chesscom.auth import ChessComCookieAuth
from chessclub.providers.chesscom.client import ChessComClient
from chessclub.services.club_service import ClubService

auth = ChessComCookieAuth()          # lê ~/.config/chessclub/credentials.json
client = ChessComClient("meu-app/1.0", auth=auth)
service = ClubService(client)
```

### Exemplos

**Info do clube:**

```python
club = service.get_club("clube-de-xadrez-de-jundiai")
print(club.name)           # "Clube de Xadrez de Jundiaí"
print(club.members_count)  # 752
print(club.created_at)     # 1644940255 (Unix timestamp)
```

**Membros:**

```python
members = service.get_club_members("clube-de-xadrez-de-jundiai")
for m in members:
    print(m.username, m.activity, m.joined_at)
```

**Torneios:**

```python
tournaments = service.get_club_tournaments("clube-de-xadrez-de-jundiai")
# ordenados por end_date ascending
for t in sorted(tournaments, key=lambda t: t.end_date or 0):
    print(f"#{t.id}  {t.name}  ({t.player_count} jogadores)")
```

**Jogos de um torneio:**

```python
# Buscar por nome parcial
matches = service.find_tournaments_by_name_or_id(
    "clube-de-xadrez-de-jundiai", "Fevereiro 2026"
)
tournament = matches[0]

games = service.get_tournament_games(tournament)
for g in games:
    print(f"{g.white} vs {g.black}  {g.result}  avg={g.avg_accuracy:.1f}%  {g.url}")
```

**Resultados (standings):**

```python
results = service.get_tournament_results(
    tournament.id, tournament_type=tournament.tournament_type
)
for r in results:
    print(f"#{r.position}  {r.player}  {r.score} pts")
```

**Sem autenticação** (apenas endpoints públicos):

```python
client = ChessComClient("meu-app/1.0")   # sem auth
club = service.get_club("clube-de-xadrez-de-jundiai")    # ✓ público
members = service.get_club_members("clube-de-xadrez-de-jundiai")  # ✓ público
tournaments = service.get_club_tournaments(...)           # ✗ requer auth
```

### Tratamento de erros

```python
from chessclub.core.exceptions import AuthenticationRequiredError, ProviderError

try:
    tournaments = service.get_club_tournaments("meu-clube")
except AuthenticationRequiredError:
    print("Configure credenciais com: chessclub auth setup")
except ProviderError as e:
    print(f"Erro da plataforma: {e}")
```

---

## Formatos de saída

Todos os comandos de listagem aceitam `--output`:

| Flag | Descrição |
|---|---|
| (omitida) | Tabela Rich colorida no terminal |
| `--output json` | JSON formatado, adequado para `jq` e scripts |
| `--output csv` | CSV com cabeçalho, adequado para Excel/pandas |

**Exemplo com `jq`:**

```bash
# Nomes dos torneios mais recentes
chessclub club tournaments clube-de-xadrez-de-jundiai --output json \
  | jq '[-3:][].name'

# Média de acurácia das partidas do último torneio
chessclub club tournaments clube-de-xadrez-de-jundiai --games 141 --output json \
  | jq '[.[].avg_accuracy | select(. != null)] | add/length'
```
