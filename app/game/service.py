import json
import secrets
from datetime import UTC, datetime

from app import config
from app.db import SessionLocal
from app.game.arena import arena
from app.game.rules import new_player
from app.game.words import normalize_letters
from app.models import LetterSet, Match, MatchEvent, MatchParticipant, User


def new_key(prefix: str = "") -> str:
    return prefix + secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:12].upper()


def skill_pool(raw: str | None) -> list[str]:
    codes = [code.strip() for code in (raw or "").split(",") if code.strip()]
    valid = [code for code in codes if code in config.SKILLS]
    return valid or config.SKILL_CODES


def letters_for(db, requested: str | None) -> str:
    if requested and requested.strip().lower() != "all":
        return normalize_letters(requested)
    pools = db.query(LetterSet).order_by(LetterSet.id).all()
    return pools[0].letters if pools else "AEIOURSTLND"


def build_rounds(letters: str) -> list[dict]:
    return [
        {"index": index, "letters": letters, "duration_seconds": config.ROUND_SECONDS}
        for index in range(config.ROUNDS_PER_MATCH)
    ]


def record_event(match_id: int, event: str, user_id: int, data: dict) -> None:
    db = SessionLocal()
    try:
        db.add(MatchEvent(match_id=match_id, event=event, user_id=user_id, data=json.dumps(data)[:500]))
        db.commit()
    finally:
        db.close()


def persist_result(match_id: int, reason: str, winner_id: int | None, players: dict, round_index: int) -> None:
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if match is None or match.status == "finished":
            return
        match.status = "finished"
        match.winner_id = winner_id
        match.end_reason = reason
        match.round_index = round_index
        match.ended_at = datetime.now(UTC)

        for participant in db.query(MatchParticipant).filter_by(match_id=match_id).all():
            state = players.get(participant.user_id)
            if state is None:
                continue
            participant.points = state["points"]
            participant.health = state["health"]
            participant.max_health = state["max_health"]
            participant.armor = state["armor"]
            participant.max_armor = state["max_armor"]
            participant.attack = state["attack"]
            participant.skill = state["skill"]
            user = db.get(User, participant.user_id)
            if user is not None:
                user.lifetime_learning_points += state["points"]
                if winner_id == participant.user_id:
                    user.wins += 1
                else:
                    user.losses += 1
                if match.tournament_id is not None:
                    user.tournaments_played += 1
        db.commit()
    finally:
        db.close()


def register_match(db, match: Match):
    existing = arena.get(match.id)
    participants = db.query(MatchParticipant).filter_by(match_id=match.id).all()
    users = {user.id: user for user in db.query(User).filter(User.id.in_([p.user_id for p in participants]))}
    pool = skill_pool(match.skills)
    players = {
        participant.user_id: new_player(
            participant.user_id, users[participant.user_id].username, pool
        )
        for participant in participants
        if participant.user_id in users
    }
    if existing is not None:
        for user_id, state in players.items():
            if user_id not in existing.players:
                existing.players[user_id] = state
        return existing
    return arena.create(
        match.id,
        players,
        build_rounds(match.allowed_letters),
        pool,
        on_finish=persist_result,
        on_event=record_event,
    )
