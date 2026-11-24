# english-plateform

An English learning platform built around **SpellBattle**, a real-time 1v1 spelling game.

## SpellBattle

Each player commands a tank. The tank's armor (HP bar), attack and special move are determined by the amount of points the player has. Points are earned by typing valid English words built from the letters chosen by the admin. The system decides automatically how points improve the tank; the player never allocates them manually.

### Rules

- The admin defines a pool of letters for each round. Both players receive the same letters.
- A word may only use those letters, and no letter may be repeated inside a word.
- Words are checked against an offline English dictionary bundled with the server.
- Word length determines how many points are earned: longer words are worth more.
- Earned points automatically raise armor and attack and unlock special moves.
- A valid word fires the tank at the opponent and reduces their armor.
- A battle ends immediately when a tank's armor reaches zero (KO). If all rounds are played, the player with the most points wins. Ties are resolved with a sudden-death round.

### Shortcuts

- `Ctrl + 0` — activate special move
- `Ctrl + 1` — regenerate HP (costs points, limited cooldown)

### Special moves

Specials unlock at point thresholds and each can be used once per match:

- **Drain** — decrease the opponent's points
- **Swap points** — exchange points with the opponent
- **Swap skill** — exchange your special moves with the opponent
- **Clear skill** — remove the opponent's unused special moves

## Stack

- **Backend:** Python, FastAPI, WebSocket, SQLAlchemy with SQLite
- **Frontend:** vanilla ES modules, Tailwind CSS and DaisyUI via CDN
- **Dictionary:** offline word list stored in `app/data/words.txt`

## Structure

```
app/
  config.py        settings and tunable game constants
  db.py            SQLAlchemy engine and session helpers
  models.py        database models
  auth.py          password hashing and signed session cookies
  main.py          FastAPI application entry point
  game/
    words.py       dictionary loading and word validation
    rules.py       scoring, tank stats, specials and healing
    arena.py       authoritative live match state
  routers/
    auth.py        signup, login, logout, current user
    pages.py       HTML page routes
    api.py         challenges, tournaments, leaderboard, validation
    admin.py       admin letter pools and tournaments
    ws.py          WebSocket battle endpoint
  static/          CSS and JavaScript modules
  templates/       Jinja page templates
  data/words.txt   offline English dictionary
tests/             pytest suite
run.py             uvicorn launcher
```

## Running locally

```bash
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:8000. Set `SECRET_KEY` in the environment for a real deployment. The first admin is bootstrapped from `ADMIN_EMAIL` and `ADMIN_PASSWORD` (defaults to `admin@spellbattle.local` / `admin123`).

## Checks

```bash
pytest -q
ruff check app tests
```
