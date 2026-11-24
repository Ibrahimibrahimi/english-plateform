import asyncio
import math
import time

from app import config
from app.game.rules import (
    activate_skill,
    apply_damage,
    is_blocked,
    regenerate_armor,
    regenerate_health,
    regenerate_skill,
    score_word,
    sync_player,
)
from app.game.words import is_valid_word


class LiveMatch:
    def __init__(
        self,
        match_id: int,
        players: dict[int, dict],
        rounds: list[dict],
        skill_pool: list[str],
        on_finish=None,
        on_event=None,
    ):
        self.match_id = match_id
        self.players = players
        self.rounds = rounds
        self.skill_pool = skill_pool
        self.on_finish = on_finish
        self.on_event = on_event
        self.connections: dict[int, object] = {}
        self.disconnect_tasks: dict[int, asyncio.Task] = {}
        self.status = "active" if len(players) == 2 else "waiting"
        self.round_index = -1
        self.round_deadline = 0.0
        self.submitted: dict[int, set[str]] = {uid: set() for uid in players}
        self.sudden_death = False
        self.winner_id: int | None = None
        self._timer: asyncio.Task | None = None

    def public_state(self) -> dict:
        now = time.monotonic()
        players = {}
        for uid, state in self.players.items():
            players[str(uid)] = {
                **{key: value for key, value in state.items() if key not in {"blocked_until", "health_ready_at", "armor_ready_at", "skill_ready_at"}},
                "skill_label": config.SKILLS.get(state["skill"]),
                "blocked": is_blocked(state, now),
                "health_ready_in": max(0, math.ceil(state["health_ready_at"] - now)),
                "armor_ready_in": max(0, math.ceil(state["armor_ready_at"] - now)),
            }
        return {
            "match_id": self.match_id,
            "status": self.status,
            "round_index": self.round_index,
            "total_rounds": len(self.rounds),
            "seconds_left": max(0, math.ceil(self.round_deadline - now)),
            "letters": self.rounds[self.round_index]["letters"] if self.round_index >= 0 else "",
            "winner_id": self.winner_id,
            "players": players,
        }

    def opponent_id(self, user_id: int) -> int | None:
        return next((uid for uid in self.players if uid != user_id), None)

    async def connect(self, user_id: int, websocket: object) -> bool:
        if user_id not in self.players:
            await websocket.send_json({"type": "error", "message": "You are not in this match"})
            return False
        task = self.disconnect_tasks.pop(user_id, None)
        if task is not None:
            task.cancel()
        self.players[user_id]["connected"] = True
        self.connections[user_id] = websocket
        await websocket.send_json({"type": "state", "payload": self.public_state()})
        if len(self.connections) == len(self.players) and self.status == "waiting":
            await self.start()
        return True

    def disconnect(self, user_id: int) -> None:
        self.connections.pop(user_id, None)
        if user_id not in self.players or self.status != "active":
            return
        self.players[user_id]["connected"] = False
        self.emit_event("player.disconnected", user_id, {})
        task = asyncio.create_task(self._forfeit_after_grace(user_id))
        self.disconnect_tasks[user_id] = task

    async def _forfeit_after_grace(self, user_id: int) -> None:
        await asyncio.sleep(config.RECONNECT_GRACE_SECONDS)
        if self.status == "active" and not self.players[user_id]["connected"]:
            winner = self.opponent_id(user_id)
            await self.finish("disconnect", winner_id=winner)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for uid, websocket in list(self.connections.items()):
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.connections.pop(uid, None)

    def emit_event(self, event: str, user_id: int, data: dict) -> None:
        if self.on_event is not None:
            self.on_event(self.match_id, event, user_id, data)
        asyncio.create_task(
            self.broadcast({"type": "event", "event": event, "user_id": user_id, "payload": data})
        )

    async def start(self) -> None:
        self.status = "active"
        self.emit_event("match.started", 0, {})
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
        self.emit_event("question.issued", 0, {"index": self.round_index, "letters": current["letters"]})
        await self.broadcast_state()

    async def _timer_loop(self) -> None:
        while self.status == "active":
            await asyncio.sleep(1)
            if self.round_deadline and time.monotonic() >= self.round_deadline:
                await self.broadcast({"type": "event", "event": "round.ended", "payload": {}})
                await self.next_round()

    async def broadcast_state(self) -> None:
        await self.broadcast({"type": "state", "payload": self.public_state()})

    async def _error(self, user_id: int, message: str) -> None:
        websocket = self.connections.get(user_id)
        if websocket is not None:
            await websocket.send_json({"type": "error", "message": message})

    async def submit_word(self, user_id: int, word: str, command_id: str = "") -> None:
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

        self.submitted[user_id].add(candidate)
        self.emit_event("answer.submitted", user_id, {"word": candidate, "command_id": command_id})
        actor = self.players[user_id]

        if is_blocked(actor):
            detail = "Point generation is blocked"
            gained = 0
        else:
            gained = score_word(candidate)
            actor["points"] += gained
            sync_player(actor, self.skill_pool)
            self.emit_event("points.awarded", user_id, {"word": candidate, "points": gained})
            detail = f"+{gained} points"

        opponent_id = self.opponent_id(user_id)
        knocked_out = False
        if opponent_id is not None and gained:
            opponent = self.players[opponent_id]
            apply_damage(actor, opponent)
            knocked_out = opponent["health"] == 0

        await self.broadcast(
            {
                "type": "word",
                "payload": {"user_id": user_id, "word": candidate, "points": gained, "message": detail},
            }
        )
        if knocked_out:
            await self.finish("ko", winner_id=user_id)
            return
        await self.broadcast_state()

    async def regenerate(self, user_id: int, resource: str) -> None:
        if self.status != "active":
            await self._error(user_id, "The match is not active")
            return
        player = self.players[user_id]
        actions = {
            "health": (regenerate_health, "health.regenerated", (player,)),
            "armor": (regenerate_armor, "armor.regenerated", (player,)),
            "skill": (regenerate_skill, "skill.regenerated", (player, self.skill_pool)),
        }
        if resource not in actions:
            await self._error(user_id, "Unknown resource")
            return
        func, event, args = actions[resource]
        try:
            detail = func(*args)
        except ValueError as exc:
            await self._error(user_id, str(exc))
            return
        self.emit_event(event, user_id, {"detail": detail})
        await self.broadcast({"type": "event", "event": event, "user_id": user_id, "payload": {"message": detail}})
        await self.broadcast_state()

    async def activate_skill(self, user_id: int) -> None:
        if self.status != "active":
            await self._error(user_id, "The match is not active")
            return
        opponent_id = self.opponent_id(user_id)
        if opponent_id is None:
            await self._error(user_id, "No opponent")
            return
        try:
            detail = activate_skill(self.players[user_id], self.players[opponent_id], self.skill_pool)
        except ValueError as exc:
            await self._error(user_id, str(exc))
            return
        self.emit_event("skill.activated", user_id, {"detail": detail})
        await self.broadcast(
            {"type": "event", "event": "skill.activated", "user_id": user_id, "payload": {"message": detail}}
        )
        await self.broadcast_state()

    async def finish(self, reason: str, winner_id: int | None = None) -> None:
        if self.status == "finished":
            return
        if winner_id is None and reason == "rounds":
            ordered = sorted(self.players.items(), key=lambda item: item[1]["points"], reverse=True)
            if len(ordered) == 2 and ordered[0][1]["points"] == ordered[1][1]["points"] and not self.sudden_death:
                self.sudden_death = True
                extra = dict(self.rounds[-1])
                extra["index"] = len(self.rounds)
                self.rounds.append(extra)
                await self.broadcast({"type": "event", "event": "sudden.death", "payload": {}})
                await self.next_round()
                return
            if ordered:
                winner_id = ordered[0][0]

        self.status = "finished"
        self.winner_id = winner_id
        if self._timer is not None:
            self._timer.cancel()
        for task in self.disconnect_tasks.values():
            task.cancel()
        self.emit_event("match.completed", winner_id or 0, {"reason": reason})
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
            self.on_finish(self.match_id, reason, winner_id, self.players, self.round_index + 1)


class Arena:
    def __init__(self):
        self.matches: dict[int, LiveMatch] = {}

    def create(self, match_id, players, rounds, skill_pool, on_finish=None, on_event=None) -> LiveMatch:
        match = LiveMatch(match_id, players, rounds, skill_pool, on_finish, on_event)
        self.matches[match_id] = match
        return match

    def get(self, match_id: int) -> LiveMatch | None:
        return self.matches.get(match_id)

    def remove(self, match_id: int) -> None:
        self.matches.pop(match_id, None)


arena = Arena()
