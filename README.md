# english-plateform

An English learning platform built around **SpellBattle**, a real-time 1v1 spelling game.

## SpellBattle

Two players compete by building English words from a shared set of letters. Valid words earn points and fire the player's tank at the opponent. The winner is the player with more points at the end of the match, or the player who knocks out the opponent's tank first.

### Learning loop

- The admin creates letter sets (6-12 unique letters) and tournaments.
- Every round gives both players the same letters.
- Players type English words using only those letters; letters may be reused, but a word cannot be played twice in the same round by either player.
- Words are checked against an offline English dictionary in `app/data/words.txt` (rebuilt with `scripts/build_words.py`).
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

A player holds one special move at a time. It is drawn randomly on the server from the moves allowed by the tournament or challenge. Activating a move consumes the card, except `CLEAR_OPPONENT_SKILL` which only removes the opponent's held move and keeps the user's card.

- `BLOCK_POINTS` — block the opponent's point generation for 5 seconds
- `REDUCE_POINTS_PERCENT` — reduce opponent points by 20%
- `STEAL_POINTS_RANGE` — take 12-30 points from the opponent
- `SWAP_SKILLS` — switch held moves with the opponent; fails and keeps your card if the opponent has no held move
- `CLEAR_OPPONENT_SKILL` — remove the opponent's held move

### Match flow

By default, 10 rounds of 120 seconds are played. A knockout wins immediately. After the final round the higher score wins; a tie triggers one sudden-death round. A match starts only after both players are connected, so joining a challenge or tournament match opens a waiting lobby. Disconnects allow a 30-second reconnect grace period before forfeiture. Reconnecting replaces any older browser socket for that player without disturbing the new connection. All scoring, timers, random draws and effects are decided by the server and broadcast over WebSocket.

Finished matches stay available in memory for `MATCH_RETENTION_SECONDS` (10 minutes by default) so a reconnect can load the final state. Active matches do not survive a process restart: they are marked `finished` with reason `abandoned`, while waiting matches are recreated lazily when a player connects.

## Stack

- **Backend:** Python, Flask, Flask-Sock WebSockets, SQLAlchemy with SQLite
- **Frontend:** vanilla ES modules, Tailwind CSS and DaisyUI via CDN
- **Dictionary:** offline word list vendored in the repository (`app/data/words.txt`), built from dwyl/english-words, Wordnik wordlist (MIT), and Wikipedia frequency data (MIT) via `scripts/build_words.py`

## Structure

```
app/
  configs.py         every setting and game constant (single source of truth)
  config.py          compatibility alias for configs.py
  validation.py      input sanitisation and injection-safe helpers
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

`/` home · `/play` mode chooser (friend, challenge, tournament) · `/play-with-friend` · `/play-challenge` · `/play-tournament` · `/challenge/create` · `/challenge/list` (private challenges by other players) · `/challenge/join` · `/tournament/search` · `/tournament/join` · `/players` · `/player/{id}` (public profile) · `/leaderboard` · `/practice` · `/profile` (with avatar picker) · `/playing/{id}` · `/admin` · `/admin/tournaments/new`

## Running locally

```bash
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:8000. The first admin is created from `ADMIN_EMAIL` and `ADMIN_PASSWORD` (defaults: `admin@spellbattle.local` / `admin123`).

A default public tournament (`SpellBattle Open`, 20 max players) is created on
first boot. Players receive a persisted, realtime notification when someone
challenges them or joins their challenge, and can pick a profile picture from
the presets defined in `configs.py`.

All tunable values (letter limits per challenge/tournament, player limits,
word scoring, skill effects, validation bounds, avatar choices and leaderboard
limits) are defined in `app/configs.py`. Deployment-specific overrides still
come from environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | local SQLite file | SQLAlchemy database URL |
| `SECRET_KEY` | development value | Signs session cookies; always set this in production |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | local defaults | Bootstrap admin account |
| `SESSION_COOKIE_SECURE` | off | Set to `1` when serving over HTTPS |
| `ALLOWED_ORIGINS` | empty | Comma-separated extra WebSocket origins beyond the same origin |
| `WS_MAX_MESSAGE_SIZE` | `4096` | Maximum WebSocket message size |
| `MATCH_RETENTION_SECONDS` | `600` | How long finished live matches stay in memory |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | `run.py` bind address |

## Production

The live match registry and presence tracking are in-process, so run exactly **one** Gunicorn worker with multiple threads:

```bash
SECRET_KEY="replace-me" SESSION_COOKIE_SECURE=1 \
  gunicorn -w 1 --threads 16 -b 0.0.0.0:8000 "app.main:app"
```

Use a reverse proxy that forwards WebSocket upgrades. If the public origin differs from the backend origin, include it in `ALLOWED_ORIGINS`.

## Checks

```bash
pytest -q
ruff check app tests
```

The test suite includes an end-to-end WebSocket round trip against a temporary threaded server.
