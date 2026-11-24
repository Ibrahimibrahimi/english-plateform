import asyncio
import math
import time

from app.game.rules import heal as heal_player
from app.game.rules import score_word, sync_player, use_special
from app.game.words import is_valid_word


class LiveMatch:
    def __init__(self, match_id: int, players: dict[int, dict], rounds: list[dict], on_finish=None):
        self.match_id = match_id
        self.players = players
        self.rounds = rounds
        self.on_finish = on_finish
        self.connections: dict[int, object] = {}
        self.status = "active" if len(players) == 2 else "waiting"
        self.round_index = -1
        self.round_deadline = 0.0
        self.submitted: dict[int, set[str]] = {uid: set() for uid in players}
        self.sudden_death = False
        self.winner_id: int | None = None
        self._timer: asyncio.Task | None = None

    def public_state(self) -> dict:
        return {
            "match_id": self.match_id,
            "status": self.status,
            "round_index": self.round_index,
            "total_rounds": len(self.rounds),
            "seconds_left": max(0, math.ceil(self.round_deadline - time.monotonic())),
            "letters": self.rounds[self.round_index]["letters"] if self.round_index >= 0 else "",
            "winner_id": self.winner_id,
            "players": {str(uid): dict(state) for uid, state in self.players.items()},
        }

    def opponent_id(self, user_id: int) -> int | None:
        for uid in self.players:
            if uid != user_id:
                return uid
        return None

    async def connect(self, user_id: int, websocket: object) -> bool:
        if user_id not in self.players:
            await websocket.send_json({"type": "error", "message": "You are not in this match"})
            return False
        self.connections[user_id] = websocket
        await websocket.send_json({"type": "state", "payload": self.public_state()})
        if len(self.connections) == len(self.players) and self.status == "waiting":
            await self.start()
        return True

    def disconnect(self, user_id: int) -> None:
        self.connections.pop(user_id, None)
        if self.status == "active" and len(self.connections) == 1:
            remaining = next(iter(self.connections))
            asyncio.create_task(self.finish("disconnect", winner_id=remaining))

    async def broadcast(self, message: dict) -> None:
        dead = []
        for uid, websocket in list(self.connections.items()):
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.connections.pop(uid, None)

    async def start(self) -> None:
        self.status = "active"
        self._timer = asyncio.create_task(self._timer_loop())
        await self.next_round()

    async def next_round(self) -> None:
        self.round_index += 1
        if self.round_index >= len(self.rounds):
            await self.finish("rounds")
            return
        current = self.rounds[self.round_index]
        self.round_deadline = time.monotonic() + current["duration_seconds"]
        self.submitted = {uid: set() for uid in self.players}
        await self.broadcast(
            {
                "type": "round_start",
                "payload": {
                    "index": self.round_index,
                    "total": len(self.rounds),
                    "letters": current["letters"],
                    "duration": current["duration_seconds"],
                },
            }
        )
        await self.broadcast_state()

    async def _timer_loop(self) -> None:
        while self.status == "active":
            await asyncio.sleep(1)
            if self.round_deadline and time.monotonic() >= self.round_deadline:
                await self.broadcast({"type": "event", "message": "Time is up"})
                await self.next_round()

    async def broadcast_state(self) -> None:
        await self.broadcast({"type": "state", "payload": self.public_state()})

    async def submit_word(self, user_id: int, word: str) -> None:
        if self.status != "active" or self.round_index < 0:
            await self._error(user_id, "The match is not active")
            return
        if time.monotonic() > self.round_deadline:
            await self._error(user_id, "The round has ended")
            return
        candidate = (word or "").strip().lower()
        letters = self.rounds[self.round_index]["letters"]
        if candidate in self.submitted[user_id]:
            await self._error(user_id, "You already used that word this round")
            return
        if not is_valid_word(candidate, letters):
            await self._error(user_id, "Invalid word")
            return

        gained = score_word(candidate)
        actor = self.players[user_id]
        actor["points"] += gained
        sync_player(actor)
        self.submitted[user_id].add(candidate)

        opponent_id = self.opponent_id(user_id)
        if opponent_id is not None:
            opponent = self.players[opponent_id]
            opponent["armor"] = max(0, opponent["armor"] - actor["attack"])
            knocked_out = opponent["armor"] == 0
        else:
            knocked_out = False

        await self.broadcast(
            {
                "type": "word",
                "payload": {"user_id": user_id, "word": candidate, "points": gained},
            }
        )
        if knocked_out:
            await self.finish("ko", winner_id=user_id)
            return
        await self.broadcast_state()

    async def use_special(self, user_id: int, name: str) -> None:
        if self.status != "active":
            await self._error(user_id, "The match is not active")
            return
        actor = self.players[user_id]
        opponent_id = self.opponent_id(user_id)
        if opponent_id is None or name not in actor["specials"]:
            await self._error(user_id, "That special is not available")
            return
        detail = use_special(name, actor, self.players[opponent_id])
        await self.broadcast({"type": "event", "message": detail})
        await self.broadcast_state()

    async def heal(self, user_id: int) -> None:
        if self.status != "active":
            await self._error(user_id, "The match is not active")
            return
        try:
            detail = heal_player(self.players[user_id])
        except ValueError as exc:
            await self._error(user_id, str(exc))
            return
        await self.broadcast({"type": "event", "message": detail})
        await self.broadcast_state()

    async def _error(self, user_id: int, message: str) -> None:
        websocket = self.connections.get(user_id)
        if websocket is not None:
            await websocket.send_json({"type": "error", "message": message})

    async def finish(self, reason: str, winner_id: int | None = None) -> None:
        if self.status == "finished":
            return
        if winner_id is None and reason == "rounds":
            ordered = sorted(self.players.items(), key=lambda item: item[1]["points"], reverse=True)
            if len(ordered) == 2 and ordered[0][1]["points"] == ordered[1][1]["points"]:
                if not self.sudden_death:
                    self.sudden_death = True
                    extra = dict(self.rounds[-1])
                    extra["index"] = len(self.rounds)
                    self.rounds.append(extra)
                    await self.broadcast({"type": "event", "message": "Tie! Sudden death round"})
                    await self.next_round()
                    return
            if ordered:
                winner_id = ordered[0][0]

        self.status = "finished"
        self.winner_id = winner_id
        if self._timer is not None:
            self._timer.cancel()
        await self.broadcast(
            {
                "type": "match_end",
                "payload": {
                    "reason": reason,
                    "winner_id": winner_id,
                    "players": {str(uid): dict(state) for uid, state in self.players.items()},
                },
            }
        )
        if self.on_finish is not None:
            self.on_finish(self.match_id, winner_id, self.players, self.round_index + 1)


class Arena:
    def __init__(self):
        self.matches: dict[int, LiveMatch] = {}

    def create(self, match_id: int, players: dict[int, dict], rounds: list[dict], on_finish=None) -> LiveMatch:
        match = LiveMatch(match_id, players, rounds, on_finish)
        self.matches[match_id] = match
        return match

    def get(self, match_id: int) -> LiveMatch | None:
        return self.matches.get(match_id)

    def remove(self, match_id: int) -> None:
        self.matches.pop(match_id, None)


arena = Arena()
