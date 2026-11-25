# english-plateform

An English learning platform built around **SpellBattle**, a real-time 1v1 spelling game.

## SpellBattle

Two players compete by building English words from a shared set of letters. Valid words earn points and fire the player's tank at the opponent. The winner is the player with more points at the end of the match, or the player who knocks out the opponent's tank first.

### Learning loop

- The admin creates letter sets (6-12 unique letters) and tournaments.
- Every round gives both players the same letters.
- Players type words using only those letters, with no letter repeated inside a word.
- Words are checked against an offline English dictionary in `app/data/words.txt`.
- Score grows with word length: 3 letters = 3 points, 4 = 6, 5 = 10, and so on.

### Tanks and resources

Points automatically improve the tank; the player never allocates them manually:

- **Health** and **armor** have configurable maximums derived from points.
- Damage is absorbed by armor first, then health. Zero health ends the match.
- Regeneration restores 20% of maximum health or 15% of maximum armor, capped at the maximum, with a point cost and cooldown.

| Shortcut | Action |
|---|---|
| `Ctrl + 0` | Activate the held special move |
| `Ctrl + 1` | Regenerate health (+20%) |
| `Ctrl + 2` | Regenerate armor (+15%) |
| `Ctrl + 3` | Draw a new random special move |

Keyboard shortcuts are ignored while typing in an input. Every action also has a clickable button.

### Special moves

A player holds one special move at a time. It is drawn randomly on the server from the moves allowed by the tournament or challenge, and activating it consumes the card.

- `BLOCK_POINTS` — block the opponent's point generation for 5 seconds
- `REDUCE_POINTS_PERCENT` — reduce opponent points by 20%
- `STEAL_POINTS_RANGE` — take 12-30 points from the opponent
- `SWAP_SKILLS` — switch held moves with the opponent
- `CLEAR_OPPONENT_SKILL` — remove the opponent's held move

### Match flow

5 rounds of 60 seconds are played. A knockout wins immediately. After the final round the higher score wins; a tie triggers one sudden-death round. Disconnects allow a 30-second reconnect grace period before forfeiture. All scoring, timers, random draws and effects are decided by the server and broadcast over WebSocket.

## Stack

- **Backend:** Python, Flask, Flask-Sock WebSockets, SQLAlchemy with SQLite
- **Frontend:** vanilla ES modules, Tailwind CSS and DaisyUI via CDN
- **Dictionary:** offline word list vendored in the repository

## Structure

```
app/
  config.py          settings and game constants
  db.py              SQLAlchemy engine and session helpers
  models.py          accounts, tournaments, challenges, matches, events
  auth.py            password hashing and signed session cookies
  main.py            Flask application and bootstrapping
  game/
    words.py         dictionary loading and validation
    rules.py         scoring, stats, regeneration and skill effects
    arena.py         authoritative live match state
    service.py       match setup and result persistence
    presence.py      online player tracking
  routers/           auth, REST API, admin, pages, WebSocket
  static/js/         vanilla ES modules
  static/css/        custom styling
  templates/         Jinja pages
  data/words.txt     offline dictionary
tests/               pytest suite
run.py               Flask launcher
```

## Pages

`/` home · `/play` mode chooser (friend, challenge, tournament) · `/play-with-friend` · `/play-challenge` · `/play-tournament` · `/challenge/create` · `/challenge/join` · `/tournament/search` · `/tournament/join` · `/players` · `/leaderboard` · `/practice` · `/profile` · `/playing/{id}` · `/admin`

## Running locally

```bash
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:8000. Set `SECRET_KEY` in the environment for a real deployment. The first admin is created from `ADMIN_EMAIL` and `ADMIN_PASSWORD` (defaults: `admin@spellbattle.local` / `admin123`).

## Checks

```bash
pytest -q
ruff check app tests
```
