from datetime import UTC, datetime

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import config
from app.auth import (
    public_profile,
    public_user,
    require_admin,
    require_user,
    validate_username,
)
from app.db import begin_immediate
from app.game.arena import arena
from app.game.presence import online_ids, touch
from app.game.rules import score_word
from app.game.service import (
    ensure_match,
    letters_for,
    new_key,
    register_match,
    skill_pool,
)
from app.game.words import is_valid_word
from app.models import (
    Challenge,
    Match,
    MatchParticipant,
    Tournament,
    TournamentParticipant,
    User,
)

router = Blueprint("api", __name__, url_prefix="/api")


def body():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _match_info(match: Match) -> dict:
    return {
        "id": match.id,
        "mode": match.mode,
        "status": match.status,
        "tournament_id": match.tournament_id,
        "challenge_id": match.challenge_id,
        "url": f"/playing/{match.id}",
    }


def _create_match(db, user_ids: list[int], letters: str, skills: str, mode: str, **extra) -> Match:
    match = Match(
        key=new_key("M"),
        mode=mode,
        allowed_letters=letters,
        skills=",".join(skill_pool(skills)),
        **extra,
    )
    db.add(match)
    db.flush()
    for user_id in user_ids:
        db.add(MatchParticipant(match_id=match.id, user_id=user_id))
    db.flush()
    return match


@router.get("/me")
def me():
    user = require_user()
    touch(user.id)
    return jsonify(public_user(user))


@router.patch("/me")
def update_me():
    db = g.db
    user = require_user()
    payload = body()
    try:
        username = validate_username(payload.get("username", ""))
    except ValueError as exc:
        abort(400, description=str(exc))
    existing = db.query(User).filter(User.username == username, User.id != user.id).first()
    if existing:
        abort(409, description="Username already taken")
    user.username = username
    db.commit()
    return jsonify(public_user(user))


@router.get("/players/online")
def online_players():
    db = g.db
    user = require_user()
    online = online_ids()
    players = (
        db.query(User)
        .filter(User.id.in_(online), User.id != user.id, User.status == "active")
        .order_by(User.username)
        .all()
    )
    return jsonify([
        {
            **public_profile(player),
            "online": True,
            "points": player.lifetime_learning_points,
        }
        for player in players
    ])


@router.post("/challenges")
def create_challenge():
    db = g.db
    user = require_user()
    touch(user.id)
    payload = body()
    letters = letters_for(db, str(payload.get("allowed_letters", "all")))
    opponent_id = None
    raw_opponent = payload.get("opponent_id")
    if raw_opponent is not None:
        try:
            opponent_id = int(raw_opponent)
        except (TypeError, ValueError):
            abort(400, description="Invalid opponent")
        if opponent_id == user.id:
            abort(400, description="You cannot challenge yourself")
        opponent = db.get(User, opponent_id)
        if opponent is None or opponent.status != "active":
            abort(404, description="Opponent not found")
    challenge = Challenge(
        key=new_key("C"),
        creator_id=user.id,
        opponent_id=opponent_id,
        allowed_letters=letters,
        skills=",".join(skill_pool(str(payload.get("skills", "")))),
    )
    db.add(challenge)
    db.flush()
    match = _create_match(
        db,
        [user.id],
        letters,
        challenge.skills,
        "challenge",
        challenge_id=challenge.id,
    )
    challenge.match_id = match.id
    db.commit()
    register_match(db, match)
    return jsonify({
        "id": challenge.id,
        "key": challenge.key,
        "status": challenge.status,
        "url": f"/challenge/join?key={challenge.key}",
        "match": _match_info(match),
    })


@router.get("/challenges/<string:key>")
def get_challenge(key: str):
    db = g.db
    require_user()
    challenge = db.query(Challenge).filter(Challenge.key == key.strip().upper()).first()
    if challenge is None:
        abort(404, description="Challenge not found")
    return jsonify({
        "key": challenge.key,
        "status": challenge.status,
        "allowed_letters": challenge.allowed_letters,
        "skills": challenge.skills,
        "expires_at": challenge.expires_at.isoformat() if challenge.expires_at else None,
        "creator_id": challenge.creator_id,
        "opponent_id": challenge.opponent_id,
        "match": _match_info(db.get(Match, challenge.match_id)) if challenge.match_id else None,
    })


@router.post("/challenges/<string:key>/join")
def join_challenge(key: str):
    db = g.db
    begin_immediate(db)
    user = require_user()
    challenge = db.query(Challenge).filter(Challenge.key == key.strip().upper()).first()
    if challenge is None:
        abort(404, description="Challenge not found")
    if challenge.status != "created":
        abort(409, description="Challenge is no longer available")
    expires = challenge.expires_at.replace(tzinfo=UTC) if challenge.expires_at else None
    if expires and expires < datetime.now(UTC):
        challenge.status = "expired"
        db.commit()
        abort(410, description="Challenge expired")
    if challenge.creator_id == user.id:
        abort(400, description="You cannot join your own challenge")
    if challenge.opponent_id is not None and challenge.opponent_id != user.id:
        abort(403, description="This challenge is for another player")

    match = db.get(Match, challenge.match_id)
    if match is None:
        abort(409, description="Challenge has no match")
    if match.status != "waiting":
        abort(409, description="Challenge match has already started")
    participants = db.query(MatchParticipant).filter_by(match_id=match.id).all()
    if any(participant.user_id == user.id for participant in participants):
        abort(409, description="Already joined")
    if len(participants) >= 2:
        abort(409, description="Challenge is full")
    db.add(MatchParticipant(match_id=match.id, user_id=user.id))
    challenge.status = "joined"
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        abort(409, description="Already joined")
    register_match(db, match)
    return jsonify(_match_info(match))


@router.get("/tournaments")
def list_tournaments():
    db = g.db
    search = request.args.get("search", "").strip()
    query = db.query(Tournament)
    if search:
        query = query.filter(Tournament.name.ilike(f"%{search}%"))
    tournaments = query.order_by(Tournament.id).all()
    return jsonify([
        {
            "id": tournament.id,
            "name": tournament.name,
            "description": tournament.description,
            "status": tournament.status,
            "max_players": tournament.max_players,
            "players": db.query(func.count(TournamentParticipant.id))
            .filter(TournamentParticipant.tournament_id == tournament.id)
            .scalar(),
            "allowed_letters": tournament.allowed_letters,
            "skills": tournament.skills,
        }
        for tournament in tournaments
    ])


@router.post("/tournaments")
def create_tournament():
    db = g.db
    admin = require_admin()
    payload = body()
    name = str(payload.get("name", "")).strip()
    if not (3 <= len(name) <= 100):
        abort(400, description="Tournament name must be 3-100 characters")
    if db.query(Tournament).filter(Tournament.name == name).first():
        abort(409, description="Tournament name already exists")
    try:
        max_players = int(payload.get("max_players", 16))
    except (TypeError, ValueError):
        abort(400, description="max_players must be between 2 and 128")
    if max_players < 2 or max_players > 128:
        abort(400, description="max_players must be between 2 and 128")
    description = str(payload.get("description", "")).strip()
    if len(description) > 300:
        abort(400, description="Description must be at most 300 characters")
    letters = letters_for(db, str(payload.get("allowed_letters", "all")))
    tournament = Tournament(
        name=name,
        description=description,
        key=new_key("T"),
        max_players=max_players,
        allowed_letters=letters,
        skills=",".join(skill_pool(str(payload.get("skills", "")))),
        created_by=admin.id,
    )
    db.add(tournament)
    db.commit()
    return jsonify({"id": tournament.id, "key": tournament.key, "name": tournament.name})


@router.get("/tournaments/<int:tournament_id>")
def tournament_details(tournament_id: int):
    db = g.db
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        abort(404, description="Tournament not found")
    participants = (
        db.query(User, TournamentParticipant.status)
        .join(TournamentParticipant, User.id == TournamentParticipant.user_id)
        .filter(TournamentParticipant.tournament_id == tournament_id)
        .all()
    )
    matches = (
        db.query(Match)
        .filter(Match.tournament_id == tournament_id)
        .order_by(Match.id)
        .all()
    )
    return jsonify({
        "id": tournament.id,
        "name": tournament.name,
        "description": tournament.description,
        "status": tournament.status,
        "max_players": tournament.max_players,
        "allowed_letters": tournament.allowed_letters,
        "skills": [
            {"code": code, "label": config.SKILLS[code]} for code in skill_pool(tournament.skills)
        ],
        "participants": [
            {"id": user.id, "username": user.username, "status": status} for user, status in participants
        ],
        "matches": [_match_info(match) for match in matches],
    })


def _join_tournament(db, tournament: Tournament, user: User) -> dict:
    if tournament.status != "open":
        abort(409, description="Tournament is not open")
    existing = (
        db.query(TournamentParticipant)
        .filter_by(tournament_id=tournament.id, user_id=user.id)
        .first()
    )
    if existing:
        abort(409, description="Already joined")
    count = (
        db.query(func.count(TournamentParticipant.id))
        .filter(TournamentParticipant.tournament_id == tournament.id)
        .scalar()
    )
    if count >= tournament.max_players:
        abort(409, description="Tournament is full")

    participant = TournamentParticipant(
        tournament_id=tournament.id, user_id=user.id, status="waiting"
    )
    db.add(participant)
    db.flush()
    opponent = (
        db.query(TournamentParticipant)
        .filter(
            TournamentParticipant.tournament_id == tournament.id,
            TournamentParticipant.user_id != user.id,
            TournamentParticipant.status == "waiting",
        )
        .order_by(TournamentParticipant.id)
        .first()
    )
    result = {"tournament_id": tournament.id, "match": None}
    try:
        if opponent is not None:
            opponent.status = "matched"
            participant.status = "matched"
            match = _create_match(
                db,
                [opponent.user_id, user.id],
                tournament.allowed_letters,
                tournament.skills,
                "tournament",
                tournament_id=tournament.id,
            )
            db.commit()
            register_match(db, match)
            result["match"] = _match_info(match)
        else:
            db.commit()
    except IntegrityError:
        db.rollback()
        abort(409, description="Already joined")
    return result


@router.post("/tournaments/join")
def join_tournament_by_key():
    db = g.db
    begin_immediate(db)
    user = require_user()
    payload = body()
    key = str(payload.get("key", "")).strip().upper()
    tournament = db.query(Tournament).filter(Tournament.key == key).first()
    if tournament is None:
        abort(404, description="Invalid tournament key")
    return jsonify(_join_tournament(db, tournament, user))


@router.post("/tournaments/<int:tournament_id>/join")
def join_tournament(tournament_id: int):
    db = g.db
    begin_immediate(db)
    user = require_user()
    payload = body()
    key = str(payload.get("key", "")).strip().upper()
    tournament = db.get(Tournament, tournament_id)
    if tournament is None or tournament.key != key:
        abort(404, description="Invalid tournament key")
    return jsonify(_join_tournament(db, tournament, user))


@router.get("/matches/<int:match_id>")
def match_snapshot(match_id: int):
    db = g.db
    user = require_user()
    match = db.get(Match, match_id)
    if match is None:
        abort(404, description="Match not found")
    participant = (
        db.query(MatchParticipant)
        .filter_by(match_id=match_id, user_id=user.id)
        .first()
    )
    if participant is None and user.role != "admin":
        abort(403, description="You are not in this match")
    live = arena.get(match_id) or ensure_match(match_id)
    state = live.public_state() if live is not None else None
    return jsonify({"match": _match_info(match), "state": state})


@router.get("/me/statistics")
def statistics():
    db = g.db
    user = require_user()
    matches = (
        db.query(MatchParticipant)
        .join(Match, Match.id == MatchParticipant.match_id)
        .filter(MatchParticipant.user_id == user.id, Match.status == "finished")
        .all()
    )
    played = len(matches)
    points = sum(entry.points for entry in matches)
    return jsonify({
        "lifetime_learning_points": user.lifetime_learning_points,
        "matches_played": played,
        "wins": user.wins,
        "losses": user.losses,
        "win_rate": round(user.wins / played * 100, 1) if played else 0,
        "average_match_points": round(points / played, 1) if played else 0,
        "tournaments_played": user.tournaments_played,
        "skills": skill_pool(""),
    })


@router.get("/me/history")
def history():
    db = g.db
    user = require_user()
    rows = (
        db.query(Match, MatchParticipant)
        .join(MatchParticipant, Match.id == MatchParticipant.match_id)
        .filter(MatchParticipant.user_id == user.id, Match.status == "finished")
        .order_by(Match.id.desc())
        .all()
    )
    return jsonify([
        {
            "id": match.id,
            "mode": match.mode,
            "status": match.status,
            "points": participant.points,
            "won": match.winner_id == user.id,
            "result": match.end_reason,
            "played_at": match.created_at.isoformat() if match.created_at else None,
        }
        for match, participant in rows
    ])


@router.get("/leaderboard")
def leaderboard():
    db = g.db
    users = db.query(User).order_by(User.lifetime_learning_points.desc()).limit(50).all()
    return jsonify([
        {
            "rank": index + 1,
            "username": user.username,
            "points": user.lifetime_learning_points,
            "wins": user.wins,
        }
        for index, user in enumerate(users)
    ])


@router.post("/words/validate")
def validate_word():
    payload = body()
    word = str(payload.get("word", ""))
    letters = str(payload.get("letters", ""))
    valid = is_valid_word(word, letters)
    return jsonify({"valid": valid, "points": score_word(word.strip().lower()) if valid else 0})
