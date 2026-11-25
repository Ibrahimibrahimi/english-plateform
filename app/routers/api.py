from datetime import UTC, datetime

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import func

from app import config
from app.auth import public_user, require_admin, require_user
from app.game.arena import arena
from app.game.presence import online_ids, touch
from app.game.rules import score_word
from app.game.service import letters_for, new_key, register_match, skill_pool
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
    return request.get_json(silent=True) or {}


def _match_info(match: Match) -> dict:
    return {
        "id": match.id,
        "key": match.key,
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
    username = str(payload.get("username", "")).strip()
    if not (3 <= len(username) <= 50):
        abort(400, description="Username must be 3-50 characters")
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
            **public_user(player),
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
    opponent_id = payload.get("opponent_id")
    challenge = Challenge(
        key=new_key("C"),
        creator_id=user.id,
        opponent_id=int(opponent_id) if opponent_id is not None else None,
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
    challenge = db.query(Challenge).filter(Challenge.key == key).first()
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
    user = require_user()
    challenge = db.query(Challenge).filter(Challenge.key == key).first()
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
    if match is None or any(p.user_id == user.id for p in db.query(MatchParticipant).filter_by(match_id=match.id).all()):
        abort(409, description="Already joined")
    db.add(MatchParticipant(match_id=match.id, user_id=user.id))
    challenge.status = "joined"
    db.commit()
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
            "key": tournament.key,
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
    if len(name) < 3:
        abort(400, description="Tournament name must be at least 3 characters")
    if db.query(Tournament).filter(Tournament.name == name).first():
        abort(409, description="Tournament name already exists")
    max_players = int(payload.get("max_players", 16))
    if max_players < 2 or max_players > 128:
        abort(400, description="max_players must be between 2 and 128")
    letters = letters_for(db, str(payload.get("allowed_letters", "all")))
    tournament = Tournament(
        name=name,
        description=str(payload.get("description", "")).strip(),
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


@router.post("/tournaments/<int:tournament_id>/join")
def join_tournament(tournament_id: int):
    db = g.db
    user = require_user()
    payload = body()
    key = str(payload.get("key", "")).strip().upper()
    tournament = db.get(Tournament, tournament_id)
    if tournament is None or tournament.key != key:
        abort(404, description="Invalid tournament key")
    if tournament.status != "open":
        abort(409, description="Tournament is not open")
    existing = (
        db.query(TournamentParticipant)
        .filter_by(tournament_id=tournament_id, user_id=user.id)
        .first()
    )
    if existing:
        abort(409, description="Already joined")
    count = (
        db.query(func.count(TournamentParticipant.id))
        .filter(TournamentParticipant.tournament_id == tournament_id)
        .scalar()
    )
    if count >= tournament.max_players:
        abort(409, description="Tournament is full")

    db.add(TournamentParticipant(tournament_id=tournament_id, user_id=user.id, status="waiting"))
    db.flush()
    opponent = (
        db.query(TournamentParticipant)
        .filter(
            TournamentParticipant.tournament_id == tournament_id,
            TournamentParticipant.user_id != user.id,
            TournamentParticipant.status == "waiting",
        )
        .first()
    )
    result = {"tournament_id": tournament_id, "match": None}
    if opponent is not None:
        opponent.status = "matched"
        participant = db.query(TournamentParticipant).filter_by(
            tournament_id=tournament_id, user_id=user.id
        ).first()
        participant.status = "matched"
        match = _create_match(
            db,
            [opponent.user_id, user.id],
            tournament.allowed_letters,
            tournament.skills,
            "tournament",
            tournament_id=tournament_id,
        )
        db.commit()
        register_match(db, match)
        result["match"] = _match_info(match)
    else:
        db.commit()
    return jsonify(result)


@router.get("/matches/<int:match_id>")
def match_snapshot(match_id: int):
    db = g.db
    require_user()
    match = db.get(Match, match_id)
    if match is None:
        abort(404, description="Match not found")
    live = arena.get(match_id)
    state = live.public_state() if live is not None else None
    return jsonify({"match": _match_info(match), "state": state})


@router.get("/me/statistics")
def statistics():
    db = g.db
    user = require_user()
    matches = db.query(MatchParticipant).filter(MatchParticipant.user_id == user.id).all()
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
        .filter(MatchParticipant.user_id == user.id)
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
