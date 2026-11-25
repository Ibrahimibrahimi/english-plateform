import json
import logging
import math
import threading
import time

from app import configs
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

logger = logging.getLogger(__name__)


class LiveMatch:
    def __init__(
        self,
        match_id: int,
        players: dict[int, dict],
        rounds: list[dict],
        skill_pool: list[str],
        on_finish=None,
        on_event=None,
        on_start=None,
        on_round=None,
    ):
        self.match_id = match_id
        self.players = players
        self.rounds = rounds
        self.skill_pool = skill_pool
        self.on_finish = on_finish
        self.on_event = on_event
        self.on_start = on_start
        self.on_round = on_round
        self.connections: dict[int, object] = {}
        self.disconnect_timers: dict[int, threading.Timer] = {}
        self.status = "waiting"
        self.round_index = -1
        self.round_deadline = 0.0
        # One shared pool for the whole match: a word played by either player
        # cannot be replayed by the opponent (or by the same player).
        self.used_words: set[str] = set()
        self.sudden_death = False
        self.winner_id: int | None = None
        self._timer: threading.Timer | None = None
        self._lock = threading.RLock()
        self._send_lock = threading.Lock()
        for player in self.players.values():
            player["connected"] = False

    def public_state(self) -> dict:
        with self._lock:
            return self._public_state_locked()

    def _public_state_locked(self) -> dict:
        now = time.monotonic()
        players = {}
        for uid, state in self.players.items():
            players[str(uid)] = {
                **{
                    key: value
                    for key, value in state.items()
                    if key not in {"blocked_until", "health_ready_at", "armor_ready_at", "skill_ready_at"}
                },
                "skill_label": configs.SKILLS.get(state["skill"]),
                "blocked": is_blocked(state, now),
                "health_ready_in": max(0, math.ceil(state["health_ready_at"] - now)),
                "armor_ready_in": max(0, math.ceil(state["armor_ready_at"] - now)),
            }
        return {
            "match_id": self.match_id,
            "status": self.status,
            "round_index": self.round_index,
            "total_rounds": len(self.rounds),
            "seconds_left": max(0, math.ceil(self.round_deadline - now)) if self.round_deadline else 0,
            "letters": self.rounds[self.round_index]["letters"] if self.round_index >= 0 else "",
            "winner_id": self.winner_id,
            "players": players,
        }

    def opponent_id(self, user_id: int) -> int | None:
        return next((uid for uid in self.players if uid != user_id), None)

    def _notify(self, callback, *args) -> None:
        if callback is None:
            return
        try:
            callback(*args)
        except Exception:
            logger.exception("match callback failed for match %s", self.match_id)

    def _send(self, websocket, message: dict) -> bool:
        if websocket is None:
            return False
        try:
            with self._send_lock:
                websocket.send(json.dumps(message))
            return True
        except Exception:
            logger.debug("websocket send failed for match %s", self.match_id, exc_info=True)
            return False

    def send_to(self, user_id: int, message: dict) -> None:
        with self._lock:
            websocket = self.connections.get(user_id)
            if websocket is not None:
                self._send(websocket, message)

    def _can_start_locked(self) -> bool:
        return (
            self.status == "waiting"
            and len(self.players) == 2
            and all(uid in self.connections for uid in self.players)
        )

    def connect(self, user_id: int, websocket) -> bool:
        with self._lock:
            if user_id not in self.players:
                self._send(websocket, {"type": "error", "message": "You are not in this match"})
                return False
            old = self.connections.get(user_id)
            if old is not None and old is not websocket:
                self._send(old, {"type": "error", "message": "This player connected from another window"})
                try:
                    old.close(4000)
                except Exception:
                    logger.debug("old websocket close failed", exc_info=True)
            timer = self.disconnect_timers.pop(user_id, None)
            if timer is not None:
                timer.cancel()
            self.players[user_id]["connected"] = True
            self.connections[user_id] = websocket
            self._send(websocket, {"type": "state", "payload": self._public_state_locked()})
            if self._can_start_locked():
                self._start_locked()
            else:
                self._broadcast_locked({"type": "state", "payload": self._public_state_locked()})
            return True

    def disconnect(self, user_id: int, websocket=None) -> None:
        with self._lock:
            self._drop_connection_locked(user_id, websocket)

    def _drop_connection_locked(self, user_id: int, websocket=None) -> bool:
        current = self.connections.get(user_id)
        if websocket is not None and current is not websocket:
            return False
        if current is None:
            return False
        self.connections.pop(user_id, None)
        player = self.players.get(user_id)
        if player is not None:
            player["connected"] = False
        if self.status != "active":
            return True
        timer = self.disconnect_timers.pop(user_id, None)
        if timer is not None:
            timer.cancel()
        self.emit_event("player.disconnected", user_id, {})
        self._broadcast_locked({"type": "state", "payload": self._public_state_locked()})
        self._schedule_forfeit_locked(user_id)
        return True

    def _schedule_forfeit_locked(self, user_id: int) -> None:
        timer = threading.Timer(
            configs.RECONNECT_GRACE_SECONDS,
            self._forfeit_after_grace,
            args=(user_id,),
        )
        timer.daemon = True
        self.disconnect_timers[user_id] = timer
        timer.start()

    def _forfeit_after_grace(self, user_id: int) -> None:
        with self._lock:
            if self.status != "active":
                return
            if self.players.get(user_id, {}).get("connected"):
                return
            opponent = self.opponent_id(user_id)
            opponent_connected = (
                opponent is not None
                and bool(self.players.get(opponent, {}).get("connected"))
            )
            if opponent_connected:
                self._finish_locked("disconnect", winner_id=opponent)
            else:
                self._finish_locked("abandoned", winner_id=None)

    def broadcast(self, message: dict) -> None:
        with self._lock:
            self._broadcast_locked(message)

    def _broadcast_locked(self, message: dict) -> None:
        dead = []
        for uid, websocket in list(self.connections.items()):
            if not self._send(websocket, message):
                dead.append(uid)
        for uid in dead:
            self._drop_connection_locked(uid)

    def emit_event(self, event: str, user_id: int, data: dict) -> None:
        with self._lock:
            self._notify(self.on_event, self.match_id, event, user_id, data)
            self._broadcast_locked(
                {"type": "event", "event": event, "user_id": user_id, "payload": data}
            )

    def add_player(self, user_id: int, state: dict) -> bool:
        with self._lock:
            if self.status != "waiting" or user_id in self.players:
                return False
            state["connected"] = False
            self.players[user_id] = state
            return True

    def start(self) -> None:
        with self._lock:
            self._start_locked()

    def _start_locked(self) -> None:
        if self.status != "waiting" or len(self.players) != 2:
            return
        if not all(uid in self.connections for uid in self.players):
            return
        self.status = "active"
        self._notify(self.on_start, self.match_id)
        self.emit_event("match.started", 0, {})
        self._schedule_tick_locked()
        self._next_round_locked()

    def next_round(self) -> None:
        with self._lock:
            self._next_round_locked()

    def _next_round_locked(self) -> None:
        self.round_index += 1
        if self.round_index >= len(self.rounds):
            self._finish_locked("rounds")
            return
        current = self.rounds[self.round_index]
        self.round_deadline = time.monotonic() + current["duration_seconds"]
        self._notify(self.on_round, self.match_id, self.round_index)
        self._broadcast_locked(
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
        self.broadcast_state()

    def _schedule_tick_locked(self) -> None:
        timer = threading.Timer(configs.MATCH_TICK_SECONDS, self._timer_tick)
        timer.daemon = True
        self._timer = timer
        timer.start()

    def _timer_tick(self) -> None:
        with self._lock:
            if self.status != "active":
                return
            if self.round_deadline and time.monotonic() >= self.round_deadline:
                self._broadcast_locked({"type": "event", "event": "round.ended", "payload": {}})
                self._next_round_locked()
            if self.status == "active":
                self._schedule_tick_locked()

    def broadcast_state(self) -> None:
        with self._lock:
            self._broadcast_locked({"type": "state", "payload": self._public_state_locked()})

    def _error(self, user_id: int, message: str) -> None:
        with self._lock:
            websocket = self.connections.get(user_id)
            if websocket is not None:
                self._send(websocket, {"type": "error", "message": message})

    def submit_word(self, user_id: int, word: str, command_id: str = "") -> None:
        with self._lock:
            if self.status != "active" or self.round_index < 0:
                self._error(user_id, "The match is not active")
                return
            if time.monotonic() > self.round_deadline:
                self._error(user_id, "The round has ended")
                return
            candidate = (word or "").strip().lower()
            letters = self.rounds[self.round_index]["letters"]
            if candidate in self.used_words:
                self._error(user_id, "That word was already used in this match")
                return
            # Validation happens before any state change: a word that is not an
            # English dictionary word is rejected without scoring or damage.
            if not is_valid_word(candidate, letters):
                self._error(user_id, "Invalid word")
                return

            self.used_words.add(candidate)
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
            # Only a validated, unblocked word that awarded points may fire.
            # Invalid words never touch either player's health.
            if opponent_id is not None and gained:
                opponent = self.players[opponent_id]
                apply_damage(actor, opponent)
                knocked_out = opponent["health"] == 0

            self._broadcast_locked(
                {
                    "type": "word",
                    "payload": {"user_id": user_id, "word": candidate, "points": gained, "message": detail},
                }
            )
            self.broadcast_state()
            if knocked_out:
                self._finish_locked("ko", winner_id=user_id)
                return

    def regenerate(self, user_id: int, resource: str) -> None:
        with self._lock:
            if self.status != "active":
                self._error(user_id, "The match is not active")
                return
            player = self.players[user_id]
            actions = {
                "health": (regenerate_health, "health.regenerated", (player,)),
                "armor": (regenerate_armor, "armor.regenerated", (player,)),
                "skill": (regenerate_skill, "skill.regenerated", (player, self.skill_pool)),
            }
            if resource not in actions:
                self._error(user_id, "Unknown resource")
                return
            func, event, args = actions[resource]
            try:
                detail = func(*args)
            except ValueError as exc:
                self._error(user_id, str(exc))
                return
            self.emit_event(event, user_id, {"detail": detail})
            self._broadcast_locked(
                {"type": "event", "event": event, "user_id": user_id, "payload": {"message": detail}}
            )
            self.broadcast_state()

    def activate_skill(self, user_id: int) -> None:
        with self._lock:
            if self.status != "active":
                self._error(user_id, "The match is not active")
                return
            opponent_id = self.opponent_id(user_id)
            if opponent_id is None:
                self._error(user_id, "No opponent")
                return
            try:
                detail = activate_skill(self.players[user_id], self.players[opponent_id], self.skill_pool)
            except ValueError as exc:
                self._error(user_id, str(exc))
                return
            self.emit_event("skill.activated", user_id, {"detail": detail})
            self._broadcast_locked(
                {"type": "event", "event": "skill.activated", "user_id": user_id, "payload": {"message": detail}}
            )
            self.broadcast_state()

    def finish(self, reason: str, winner_id: int | None = None) -> None:
        with self._lock:
            self._finish_locked(reason, winner_id)

    def _finish_locked(self, reason: str, winner_id: int | None = None) -> None:
        if self.status == "finished":
            return
        if winner_id is None and reason == "rounds":
            ordered = sorted(self.players.items(), key=lambda item: item[1]["points"], reverse=True)
            if len(ordered) == 2 and ordered[0][1]["points"] == ordered[1][1]["points"] and not self.sudden_death:
                self.sudden_death = True
                extra = dict(self.rounds[-1])
                extra["index"] = len(self.rounds)
                self.rounds.append(extra)
                self._broadcast_locked({"type": "event", "event": "sudden.death", "payload": {}})
                self._next_round_locked()
                return
            if ordered:
                winner_id = ordered[0][0]

        self.status = "finished"
        self.winner_id = winner_id
        if self._timer is not None:
            self._timer.cancel()
        for timer in self.disconnect_timers.values():
            timer.cancel()
        self.disconnect_timers.clear()
        self.emit_event("match.completed", winner_id or 0, {"reason": reason})
        self._broadcast_locked(
            {
                "type": "match_end",
                "payload": {
                    "reason": reason,
                    "winner_id": winner_id,
                    "players": self._public_state_locked()["players"],
                },
            }
        )
        self._notify(self.on_finish, self.match_id, reason, winner_id, self.players, self.round_index + 1)


class Arena:
    def __init__(self):
        self.matches: dict[int, LiveMatch] = {}
        self._lock = threading.RLock()

    def create(
        self,
        match_id,
        players,
        rounds,
        skill_pool,
        on_finish=None,
        on_event=None,
        on_start=None,
        on_round=None,
    ) -> LiveMatch:
        def finish_and_cleanup(match_id, reason, winner_id, players_state, round_index):
            try:
                if on_finish is not None:
                    on_finish(match_id, reason, winner_id, players_state, round_index)
            finally:
                timer = threading.Timer(configs.MATCH_RETENTION_SECONDS, self.remove, args=(match_id,))
                timer.daemon = True
                timer.start()

        with self._lock:
            existing = self.matches.get(match_id)
            if existing is not None:
                return existing
            match = LiveMatch(
                match_id,
                players,
                rounds,
                skill_pool,
                on_finish=finish_and_cleanup,
                on_event=on_event,
                on_start=on_start,
                on_round=on_round,
            )
            self.matches[match_id] = match
            return match

    def get(self, match_id: int) -> LiveMatch | None:
        with self._lock:
            return self.matches.get(match_id)

    def remove(self, match_id: int) -> None:
        with self._lock:
            self.matches.pop(match_id, None)


arena = Arena()
