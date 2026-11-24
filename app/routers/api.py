from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import config
from app.auth import public_user, require_admin, require_user
from app.db import get_db
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

router = APIRouter(prefix="/api", tags=["api"])


class ProfileIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)


class ChallengeIn(BaseModel):
    opponent_id: int | None = None
    allowed_letters: str = "all"
    skills: str = ""


class JoinChallengeIn(BaseModel):
    key: str


class TournamentIn(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str = ""
    max_players: int = Field(default=16, ge=2, le=128)
    allowed_letters: str = "all"
    skills: str = ""


class JoinTournamentIn(BaseModel):
    key: str


class WordIn(BaseModel):
    word: str
    letters: str


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


def _create_match(db: Session, user_ids: list[int], letters: str, skills: str, mode: str, **extra) -> Match:
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
def me(request: Request):
    user = require_user(request)
    touch(user.id)
    return public_user(user)


@router.patch("/me")
def update_me(payload: ProfileIn, request: Request, db: Session = Depends(get_db)):
    user = require_user(request)
    username = payload.username.strip()
    existing = db.query(User).filter(User.username == username, User.id != user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    user.username = username
    db.commit()
    return public_user(user)


@router.get("/players/online")
def online_players(request: Request, db: Session = Depends(get_db)):
    user = require_user(request)
    online = online_ids()
    players = (
        db.query(User)
        .filter(User.id.in_(online), User.id != user.id, User.status == "active")
        .order_by(User.username)
        .all()
    )
    return [
        {
            **public_user(player),
            "online": True,
            "points": player.lifetime_learning_points,
        }
        for player in players
    ]


@router.post("/challenges")
def create_challenge(payload: ChallengeIn, request: Request, db: Session = Depends(get_db)):
    user = require_user(request)
    touch(user.id)
    letters = letters_for(db, payload.allowed_letters)
    challenge = Challenge(
        key=new_key("C"),
        creator_id=user.id,
        opponent_id=payload.opponent_id,
        allowed_letters=letters,
        skills=",".join(skill_pool(payload.skills)),
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
    return {
        "id": challenge.id,
        "key": challenge.key,
        "status": challenge.status,
        "url": f"/challenge/join?key={challenge.key}",
        "match": _match_info(match),
    }


@router.get("/challenges/{key}")
def get_challenge(key: str, db: Session = Depends(get_db)):
    challenge = db.query(Challenge).filter(Challenge.key == key).first()
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return {
        "key": challenge.key,
        "status": challenge.status,
        "allowed_letters": challenge.allowed_letters,
        "skills": challenge.skills,
        "expires_at": challenge.expires_at,
        "creator_id": challenge.creator_id,
        "opponent_id": challenge.opponent_id,
        "match": _match_info(db.get(Match, challenge.match_id)) if challenge.match_id else None,
    }


@router.post("/challenges/{key}/join")
def join_challenge(key: str, request: Request, db: Session = Depends(get_db)):
    user = require_user(request)
    challenge = db.query(Challenge).filter(Challenge.key == key).first()
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if challenge.status != "created":
        raise HTTPException(status_code=409, detail="Challenge is no longer available")
    if challenge.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        challenge.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="Challenge expired")
    if challenge.creator_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot join your own challenge")
    if challenge.opponent_id is not None and challenge.opponent_id != user.id:
        raise HTTPException(status_code=403, detail="This challenge is for another player")

    match = db.get(Match, challenge.match_id)
    if match is None or any(p.user_id == user.id for p in db.query(MatchParticipant).filter_by(match_id=match.id).all()):
        raise HTTPException(status_code=409, detail="Already joined")
    db.add(MatchParticipant(match_id=match.id, user_id=user.id))
    challenge.status = "joined"
    db.commit()
    register_match(db, match)
    return _match_info(match)


@router.get("/tournaments")
def list_tournaments(search: str = "", db: Session = Depends(get_db)):
    query = db.query(Tournament)
    if search:
        query = query.filter(Tournament.name.ilike(f"%{search}%"))
    tournaments = query.order_by(Tournament.id).all()
    return [
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
    ]


@router.post("/tournaments")
def create_tournament(payload: TournamentIn, request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request)
    if db.query(Tournament).filter(Tournament.name == payload.name.strip()).first():
        raise HTTPException(status_code=409, detail="Tournament name already exists")
    letters = letters_for(db, payload.allowed_letters)
    tournament = Tournament(
        name=payload.name.strip(),
        description=payload.description.strip(),
        key=new_key("T"),
        max_players=payload.max_players,
        allowed_letters=letters,
        skills=",".join(skill_pool(payload.skills)),
        created_by=admin.id,
    )
    db.add(tournament)
    db.commit()
    return {"id": tournament.id, "key": tournament.key, "name": tournament.name}


@router.get("/tournaments/{tournament_id}")
def tournament_details(tournament_id: int, db: Session = Depends(get_db)):
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="Tournament not found")
    participants = (
        db.query(User, TournamentParticipant.status)
        .join(TournamentParticipant, User.id == TournamentParticipant.user_id)
        .filter(TournamentParticipant.tournament_id == tournament_id)
        .all()
    )
    return {
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
    }


@router.post("/tournaments/{tournament_id}/join")
def join_tournament(tournament_id: int, payload: JoinTournamentIn, request: Request, db: Session = Depends(get_db)):
    user = require_user(request)
    tournament = db.get(Tournament, tournament_id)
    if tournament is None or tournament.key != payload.key.strip().upper():
        raise HTTPException(status_code=404, detail="Invalid tournament key")
    if tournament.status != "open":
        raise HTTPException(status_code=409, detail="Tournament is not open")
    existing = (
        db.query(TournamentParticipant)
        .filter_by(tournament_id=tournament_id, user_id=user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already joined")
    count = (
        db.query(func.count(TournamentParticipant.id))
        .filter(TournamentParticipant.tournament_id == tournament_id)
        .scalar()
    )
    if count >= tournament.max_players:
        raise HTTPException(status_code=409, detail="Tournament is full")

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
    return result


@router.get("/matches/{match_id}")
def match_snapshot(match_id: int, request: Request, db: Session = Depends(get_db)):
    require_user(request)
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    live = arena.get(match_id)
    state = live.public_state() if live is not None else None
    return {"match": _match_info(match), "state": state}


@router.get("/me/statistics")
def statistics(request: Request, db: Session = Depends(get_db)):
    user = require_user(request)
    matches = db.query(MatchParticipant).filter(MatchParticipant.user_id == user.id).all()
    played = len(matches)
    points = sum(entry.points for entry in matches)
    return {
        "lifetime_learning_points": user.lifetime_learning_points,
        "matches_played": played,
        "wins": user.wins,
        "losses": user.losses,
        "win_rate": round(user.wins / played * 100, 1) if played else 0,
        "average_match_points": round(points / played, 1) if played else 0,
        "tournaments_played": user.tournaments_played,
        "skills": skill_pool(""),
    }


@router.get("/me/history")
def history(request: Request, db: Session = Depends(get_db)):
    user = require_user(request)
    rows = (
        db.query(Match, MatchParticipant)
        .join(MatchParticipant, Match.id == MatchParticipant.match_id)
        .filter(MatchParticipant.user_id == user.id)
        .order_by(Match.id.desc())
        .all()
    )
    return [
        {
            "id": match.id,
            "mode": match.mode,
            "status": match.status,
            "points": participant.points,
            "won": match.winner_id == user.id,
            "result": match.end_reason,
            "played_at": match.created_at,
        }
        for match, participant in rows
    ]


@router.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.lifetime_learning_points.desc()).limit(50).all()
    return [
        {
            "rank": index + 1,
            "username": user.username,
            "points": user.lifetime_learning_points,
            "wins": user.wins,
        }
        for index, user in enumerate(users)
    ]


@router.post("/words/validate")
def validate_word(payload: WordIn):
    valid = is_valid_word(payload.word, payload.letters)
    return {"valid": valid, "points": score_word(payload.word.strip().lower()) if valid else 0}
