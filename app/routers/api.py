import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import configs
from app.auth import (
    avatar_info,
    current_user,
    public_profile,
    public_user,
    require_admin,
    require_user,
    validate_username,
)
from app.db import begin_immediate
from app.game.arena import arena
from app.game.notifications import notification_hub
from app.game.presence import online_ids, touch
from app.game.rules import score_word
from app.game.service import (
    ensure_match,
    letters_for,
    new_key,
    register_match,
    skill_pool,
)
from app.game.tournaments import create_tournament as build_tournament
from app.game.words import is_valid_word
from app.models import (
    Challenge,
    FriendRequest,
    Match,
    MatchParticipant,
    Notification,
    RematchOffer,
    Tournament,
    TournamentParticipant,
    User,
)
from app.validation import (
    clean_avatar,
    clean_avatar_upload,
    clean_key,
    clean_search,
    clean_text,
)

router = Blueprint("api", __name__, url_prefix="/api")


def body():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _remove_avatar_file(user_id: int, filename: str | None) -> None:
    if not filename or "/" in filename or "\\" in filename:
        return
    if not filename.startswith(f"avatar-{user_id}-"):
        return
    if Path(filename).suffix.lstrip(".") not in configs.AVATAR_UPLOAD_EXTENSIONS:
        return
    (configs.UPLOAD_DIR / filename).unlink(missing_ok=True)


def _notify(db, user_id: int, kind: str, message: str, link: str, data: dict | None = None) -> Notification:
    """Persist a notification and push it to any open notification socket."""
    entry = Notification(
        user_id=user_id,
        type=kind,
        message=clean_text(message, configs.NOTIFICATION_MESSAGE_MAX_LENGTH),
        link=clean_text(link, configs.NOTIFICATION_MESSAGE_MAX_LENGTH),
        data=json.dumps(data or {})[: configs.EVENT_DATA_MAX_LENGTH],
    )
    db.add(entry)
    db.flush()
    notification_hub.send(
        user_id,
        {
            "type": "notification",
            "payload": {
                "id": entry.id,
                "type": entry.type,
                "message": entry.message,
                "link": entry.link,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            },
        },
    )
    return entry


def _notification_json(entry: Notification) -> dict:
    return {
        "id": entry.id,
        "type": entry.type,
        "message": entry.message,
        "link": entry.link,
        "read": bool(entry.read),
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def _friend_request(db, first_id: int, second_id: int) -> FriendRequest | None:
    return (
        db.query(FriendRequest)
        .filter(
            ((FriendRequest.from_id == first_id) & (FriendRequest.to_id == second_id))
            | ((FriendRequest.from_id == second_id) & (FriendRequest.to_id == first_id))
        )
        .order_by(FriendRequest.id.desc())
        .first()
    )


def _friend_status(db, viewer_id: int | None, other_id: int) -> str:
    if viewer_id is None or viewer_id == other_id:
        return "self" if viewer_id == other_id else "none"
    request_row = _friend_request(db, viewer_id, other_id)
    if request_row is None or request_row.status == configs.FRIEND_STATUS_DECLINED:
        return "none"
    if request_row.status == configs.FRIEND_STATUS_ACCEPTED:
        return "friends"
    return "incoming" if request_row.to_id == viewer_id else "outgoing"


def _friend_request_json(db, request_row: FriendRequest, viewer_id: int) -> dict:
    other_id = request_row.to_id if request_row.from_id == viewer_id else request_row.from_id
    other = db.get(User, other_id)
    return {
        "id": request_row.id,
        "status": request_row.status,
        "direction": "outgoing" if request_row.from_id == viewer_id else "incoming",
        "user": public_profile(other) if other else None,
        "created_at": request_row.created_at.isoformat() if request_row.created_at else None,
    }


def _rematch_json(db, offer: RematchOffer, viewer_id: int) -> dict:
    sender = db.get(User, offer.from_id)
    new_match = db.get(Match, offer.new_match_id) if offer.new_match_id else None
    return {
        "id": offer.id,
        "status": offer.status,
        "direction": "outgoing" if offer.from_id == viewer_id else "incoming",
        "from": public_profile(sender) if sender else None,
        "can_accept": offer.to_id == viewer_id and offer.status == configs.REMATCH_STATUS_PENDING,
        "new_match": _match_info(new_match) if new_match else None,
        "url": f"/playing/{new_match.id}" if new_match else None,
        "expires_at": offer.expires_at.isoformat() if offer.expires_at else None,
    }


def _match_info(match: Match) -> dict:
    return {
        "id": match.id,
        "mode": match.mode,
        "status": match.status,
        "tournament_id": match.tournament_id,
        "challenge_id": match.challenge_id,
        "start_delay_seconds": match.start_delay_seconds,
        "end_mode": match.end_mode,
        "url": f"/playing/{match.id}",
    }


def _challenge_timing(payload: dict) -> tuple[int, str]:
    try:
        delay = int(payload.get("start_delay_seconds", configs.CHALLENGE_DELAY_DEFAULT_SECONDS))
    except (TypeError, ValueError):
        abort(400, description="Invalid start delay")
    if not configs.CHALLENGE_DELAY_MIN_SECONDS <= delay <= configs.CHALLENGE_DELAY_MAX_SECONDS:
        abort(400, description="Invalid start delay")
    end_mode = str(payload.get("end_mode", configs.CHALLENGE_END_MODE_ROUNDS))
    if end_mode not in configs.CHALLENGE_END_MODES:
        abort(400, description="Invalid match length")
    return delay, end_mode


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


@router.get("/config")
def public_config():
    """Public settings so the browser never needs its own copy of the rules."""
    return jsonify({
        "skills": [
            {"code": code, "label": label, "icon": configs.SKILL_ICONS.get(code, "✨")}
            for code, label in configs.SKILLS.items()
        ],
        "avatars": configs.AVATARS,
        "default_avatar": configs.DEFAULT_AVATAR,
        "max_avatar_bytes": configs.AVATAR_UPLOAD_MAX_BYTES,
        "default_letters": configs.DEFAULT_LETTERS,
        "challenge_min_letters": configs.CHALLENGE_MIN_LETTERS,
        "challenge_max_letters": configs.CHALLENGE_MAX_LETTERS,
        "challenge_delay_min": configs.CHALLENGE_DELAY_MIN_SECONDS,
        "challenge_delay_max": configs.CHALLENGE_DELAY_MAX_SECONDS,
        "challenge_end_modes": configs.CHALLENGE_END_MODES,
        "tournament_min_letters": configs.TOURNAMENT_MIN_LETTERS,
        "tournament_max_letters": configs.TOURNAMENT_MAX_LETTERS,
        "min_players": configs.MIN_TOURNAMENT_PLAYERS,
        "max_players": configs.MAX_TOURNAMENT_PLAYERS,
        "default_players": configs.DEFAULT_TOURNAMENT_MAX_PLAYERS,
        "tournament_statuses": configs.TOURNAMENT_STATUSES,
        "round_seconds": configs.ROUND_SECONDS,
        "rounds_per_match": configs.ROUNDS_PER_MATCH,
    })


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
    if "username" in payload:
        try:
            username = validate_username(payload["username"])
        except ValueError as exc:
            abort(400, description=str(exc))
        existing = db.query(User).filter(User.username == username, User.id != user.id).first()
        if existing:
            abort(409, description="Username already taken")
        user.username = username
    if "avatar" in payload:
        user.avatar = clean_avatar(payload["avatar"])
        _remove_avatar_file(user.id, user.avatar_image)
        user.avatar_image = None
    db.commit()
    return jsonify(public_user(user))


@router.post("/me/avatar")
def upload_avatar():
    user = require_user()
    data, extension = clean_avatar_upload(request.files.get("image"))
    configs.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"avatar-{user.id}-{secrets.token_hex(12)}.{extension}"
    (configs.UPLOAD_DIR / filename).write_bytes(data)
    previous = user.avatar_image
    user.avatar_image = filename
    g.db.commit()
    _remove_avatar_file(user.id, previous)
    return jsonify(public_user(user))


@router.get("/friends/count")
def friend_request_count():
    db = g.db
    user = require_user()
    count = db.query(func.count(FriendRequest.id)).filter(
        FriendRequest.to_id == user.id,
        FriendRequest.status == configs.FRIEND_STATUS_PENDING,
    ).scalar()
    return jsonify({"count": count})


@router.get("/friends")
def list_friends():
    db = g.db
    user = require_user()
    accepted = (
        db.query(FriendRequest)
        .filter(
            FriendRequest.status == configs.FRIEND_STATUS_ACCEPTED,
            (FriendRequest.from_id == user.id) | (FriendRequest.to_id == user.id),
        )
        .all()
    )
    friend_ids = [row.to_id if row.from_id == user.id else row.from_id for row in accepted]
    friends = (
        db.query(User)
        .filter(User.id.in_(friend_ids), User.status == "active")
        .order_by(User.username)
        .all()
    )
    incoming = (
        db.query(FriendRequest)
        .filter(
            FriendRequest.to_id == user.id,
            FriendRequest.status == configs.FRIEND_STATUS_PENDING,
        )
        .order_by(FriendRequest.id.desc())
        .all()
    )
    outgoing = (
        db.query(FriendRequest)
        .filter(
            FriendRequest.from_id == user.id,
            FriendRequest.status == configs.FRIEND_STATUS_PENDING,
        )
        .order_by(FriendRequest.id.desc())
        .all()
    )
    return jsonify({
        "friends": [public_profile(friend) for friend in friends],
        "incoming": [_friend_request_json(db, row, user.id) for row in incoming],
        "outgoing": [_friend_request_json(db, row, user.id) for row in outgoing],
    })


@router.post("/friends/requests")
def send_friend_request():
    db = g.db
    begin_immediate(db)
    user = require_user()
    try:
        target_id = int(body().get("user_id"))
    except (TypeError, ValueError):
        abort(400, description="Invalid player")
    if target_id == user.id:
        abort(400, description="You cannot friend yourself")
    target = db.get(User, target_id)
    if target is None or target.status != "active":
        abort(404, description="Player not found")

    existing = _friend_request(db, user.id, target_id)
    if existing and existing.status == configs.FRIEND_STATUS_ACCEPTED:
        abort(409, description="You are already friends")
    if existing and existing.status == configs.FRIEND_STATUS_PENDING:
        abort(409, description="A friend request is already pending")
    if existing:
        existing.from_id = user.id
        existing.to_id = target_id
        existing.status = configs.FRIEND_STATUS_PENDING
        existing.updated_at = datetime.now(UTC).replace(tzinfo=None)
    else:
        existing = FriendRequest(from_id=user.id, to_id=target_id)
        db.add(existing)
    db.flush()
    _notify(
        db,
        target_id,
        configs.NOTIFICATION_FRIEND_REQUEST_RECEIVED,
        f"{user.username} sent you a friend request",
        "/friends",
        {"request_id": existing.id, "from_id": user.id},
    )
    db.commit()
    return jsonify(_friend_request_json(db, existing, user.id)), 201


@router.post("/friends/requests/<int:request_id>/accept")
def accept_friend_request(request_id: int):
    db = g.db
    begin_immediate(db)
    user = require_user()
    request_row = db.get(FriendRequest, request_id)
    if request_row is None:
        abort(404, description="Friend request not found")
    if request_row.to_id != user.id:
        abort(403, description="This request is not for you")
    if request_row.status != configs.FRIEND_STATUS_PENDING:
        abort(409, description="Friend request is no longer pending")
    request_row.status = configs.FRIEND_STATUS_ACCEPTED
    request_row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    sender = db.get(User, request_row.from_id)
    _notify(
        db,
        request_row.from_id,
        configs.NOTIFICATION_FRIEND_REQUEST_ACCEPTED,
        f"{user.username} accepted your friend request",
        "/friends",
        {"request_id": request_row.id, "user_id": user.id},
    )
    db.commit()
    return jsonify({"id": request_row.id, "status": request_row.status, "friend": public_profile(sender) if sender else None})


@router.post("/friends/requests/<int:request_id>/decline")
def decline_friend_request(request_id: int):
    db = g.db
    begin_immediate(db)
    user = require_user()
    request_row = db.get(FriendRequest, request_id)
    if request_row is None:
        abort(404, description="Friend request not found")
    if request_row.to_id != user.id:
        abort(403, description="This request is not for you")
    if request_row.status != configs.FRIEND_STATUS_PENDING:
        abort(409, description="Friend request is no longer pending")
    request_row.status = configs.FRIEND_STATUS_DECLINED
    request_row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    sender = db.get(User, request_row.from_id)
    _notify(
        db,
        request_row.from_id,
        configs.NOTIFICATION_FRIEND_REQUEST_DECLINED,
        f"{user.username} declined your friend request",
        "/friends",
        {"request_id": request_row.id, "user_id": user.id},
    )
    db.commit()
    return jsonify({"id": request_row.id, "status": request_row.status, "user": public_profile(sender) if sender else None})


@router.delete("/friends/<int:user_id>")
def remove_friend(user_id: int):
    db = g.db
    begin_immediate(db)
    user = require_user()
    request_row = _friend_request(db, user.id, user_id)
    if request_row is None or request_row.status != configs.FRIEND_STATUS_ACCEPTED:
        abort(404, description="Friend not found")
    request_row.status = configs.FRIEND_STATUS_DECLINED
    request_row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return jsonify({"status": "ok"})


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
            "friend_status": _friend_status(db, user.id, player.id),
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
    delay, end_mode = _challenge_timing(payload)
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
        start_delay_seconds=delay,
        end_mode=end_mode,
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
        start_delay_seconds=delay,
        end_mode=end_mode,
    )
    challenge.match_id = match.id
    db.commit()
    register_match(db, match)
    # Let the invited player know a challenge arrived (persisted + realtime).
    if opponent_id is not None:
        _notify(
            db,
            opponent_id,
            configs.NOTIFICATION_CHALLENGE_RECEIVED,
            f"{user.username} sent you a private challenge",
            f"/challenge/join?key={challenge.key}",
            {"challenge_id": challenge.id, "creator_id": user.id},
        )
        db.commit()
    return jsonify({
        "id": challenge.id,
        "key": challenge.key,
        "status": challenge.status,
        "start_delay_seconds": challenge.start_delay_seconds,
        "end_mode": challenge.end_mode,
        "url": f"/challenge/join?key={challenge.key}",
        "match": _match_info(match),
    })


@router.get("/challenges")
def list_challenges():
    """List joinable private challenges created by other players."""
    db = g.db
    user = require_user()
    now = datetime.now(UTC).replace(tzinfo=None)
    challenges = (
        db.query(Challenge, User)
        .join(User, User.id == Challenge.creator_id)
        .filter(
            Challenge.status == "created",
            Challenge.creator_id != user.id,
            (Challenge.expires_at.is_(None) | (Challenge.expires_at > now)),
            (Challenge.opponent_id.is_(None) | (Challenge.opponent_id == user.id)),
        )
        .order_by(Challenge.created_at.desc())
        .limit(configs.CHALLENGE_LIST_LIMIT)
        .all()
    )
    return jsonify([
        {
            "id": challenge.id,
            "key": challenge.key,
            "status": challenge.status,
            "allowed_letters": challenge.allowed_letters,
            "skills": challenge.skills,
            "start_delay_seconds": challenge.start_delay_seconds,
            "end_mode": challenge.end_mode,
            "for_you": challenge.opponent_id == user.id,
            "expires_at": challenge.expires_at.isoformat() if challenge.expires_at else None,
            "created_at": challenge.created_at.isoformat() if challenge.created_at else None,
            "creator": public_profile(creator),
            "join_url": f"/challenge/join?key={challenge.key}",
        }
        for challenge, creator in challenges
    ])


@router.get("/challenges/<string:key>")
def get_challenge(key: str):
    db = g.db
    require_user()
    try:
        key = clean_key(key)
    except ValueError as exc:
        abort(400, description=str(exc))
    challenge = db.query(Challenge).filter(Challenge.key == key).first()
    if challenge is None:
        abort(404, description="Challenge not found")
    return jsonify({
        "key": challenge.key,
        "status": challenge.status,
        "allowed_letters": challenge.allowed_letters,
        "skills": challenge.skills,
        "start_delay_seconds": challenge.start_delay_seconds,
        "end_mode": challenge.end_mode,
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
    try:
        key = clean_key(key)
    except ValueError as exc:
        abort(400, description=str(exc))
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
    _notify(
        db,
        challenge.creator_id,
        configs.NOTIFICATION_CHALLENGE_JOINED,
        f"{user.username} joined your challenge",
        f"/playing/{match.id}",
        {"challenge_id": challenge.id, "match_id": match.id},
    )
    db.commit()
    return jsonify(_match_info(match))


@router.get("/tournaments")
def list_tournaments():
    db = g.db
    try:
        search = clean_search(request.args.get("search", ""))
    except ValueError as exc:
        abort(400, description=str(exc))
    query = db.query(Tournament)
    if search:
        # Escaped LIKE wildcards + a bound parameter: no SQL injection.
        query = query.filter(Tournament.name.ilike(f"%{search}%", escape="\\"))
    tournaments = query.order_by(Tournament.id).all()
    return jsonify([
        {
            "id": tournament.id,
            "name": tournament.name,
            "description": tournament.description,
            "status": tournament.status,
            "requires_key": bool(tournament.requires_key),
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
    """Admin-only tournament creation (also available under /admin/api)."""
    db = g.db
    admin = require_admin()
    tournament = build_tournament(db, admin, body())
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
    viewer = current_user()
    viewer_participant = None
    viewer_match = None
    if viewer is not None:
        participant_row = (
            db.query(TournamentParticipant)
            .filter_by(tournament_id=tournament_id, user_id=viewer.id)
            .first()
        )
        if participant_row is not None:
            viewer_participant = participant_row.status
            match = (
                db.query(Match)
                .join(MatchParticipant, MatchParticipant.match_id == Match.id)
                .filter(Match.tournament_id == tournament_id, MatchParticipant.user_id == viewer.id)
                .order_by(Match.id.desc())
                .first()
            )
            if match is not None:
                viewer_match = _match_info(match)
    return jsonify({
        "id": tournament.id,
        "name": tournament.name,
        "description": tournament.description,
        "status": tournament.status,
        "requires_key": bool(tournament.requires_key),
        "max_players": tournament.max_players,
        "allowed_letters": tournament.allowed_letters,
        "skills": [
            {
                "code": code,
                "label": configs.SKILLS[code],
                "icon": configs.SKILL_ICONS.get(code, "✨"),
            }
            for code in skill_pool(tournament.skills)
        ],
        "participants": [
            {"id": user.id, "username": user.username, "status": status} for user, status in participants
        ],
        "matches": [_match_info(match) for match in matches],
        "viewer_participant": viewer_participant,
        "viewer_match": viewer_match,
    })


def _tournament_match_for_user(db, tournament_id: int, user_id: int) -> Match | None:
    return (
        db.query(Match)
        .join(MatchParticipant, MatchParticipant.match_id == Match.id)
        .filter(Match.tournament_id == tournament_id, MatchParticipant.user_id == user_id)
        .order_by(Match.id.desc())
        .first()
    )


def _eligible_waiting_tournament_match(db, tournament: Tournament, user_id: int) -> Match | None:
    now = datetime.now(UTC).replace(tzinfo=None)
    grace = max(0, configs.TOURNAMENT_WAITING_GRACE_SECONDS)
    matches = (
        db.query(Match)
        .filter(Match.tournament_id == tournament.id, Match.status == "waiting")
        .order_by(Match.id.asc())
        .all()
    )
    for match in matches:
        participants = db.query(MatchParticipant).filter_by(match_id=match.id).all()
        if len(participants) != 1:
            continue
        opponent = participants[0]
        if opponent.user_id == user_id:
            continue
        tp = (
            db.query(TournamentParticipant)
            .filter_by(tournament_id=tournament.id, user_id=opponent.user_id)
            .first()
        )
        if tp is None or tp.status != "waiting":
            continue
        live = arena.get(match.id)
        connected = bool(live and live.players.get(opponent.user_id, {}).get("connected"))
        created_at = match.created_at.replace(tzinfo=None) if match.created_at else now
        if connected or (now - created_at).total_seconds() <= grace:
            return match
    return None


def _ensure_waiting_tournament_match(db, tournament: Tournament, user: User) -> Match:
    participant = (
        db.query(TournamentParticipant)
        .filter_by(tournament_id=tournament.id, user_id=user.id)
        .first()
    )
    if participant is None:
        abort(409, description="Already joined")
    participant.status = "waiting"
    match = _create_match(
        db,
        [user.id],
        tournament.allowed_letters,
        tournament.skills,
        "tournament",
        tournament_id=tournament.id,
        start_delay_seconds=0,
        end_mode=configs.CHALLENGE_END_MODE_ROUNDS,
    )
    return match


def _join_tournament(db, tournament: Tournament, user: User) -> dict:
    existing = (
        db.query(TournamentParticipant)
        .filter_by(tournament_id=tournament.id, user_id=user.id)
        .first()
    )
    if existing is not None:
        current = _tournament_match_for_user(db, tournament.id, user.id)
        if current is not None:
            if current.status == "finished":
                abort(409, description="Already joined")
            db.commit()
            register_match(db, current)
            return {"tournament_id": tournament.id, "match": _match_info(current)}
        match = _ensure_waiting_tournament_match(db, tournament, user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            abort(409, description="Already joined")
        register_match(db, match)
        live = arena.get(match.id)
        if live is not None:
            live.arm_waiting_timeout()
        return {"tournament_id": tournament.id, "match": _match_info(match)}

    if tournament.status != "open":
        abort(409, description="Tournament is not open")
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

    waiting_match = _eligible_waiting_tournament_match(db, tournament, user.id)
    try:
        if waiting_match is not None:
            opponent_participant = (
                db.query(MatchParticipant)
                .filter(MatchParticipant.match_id == waiting_match.id, MatchParticipant.user_id != user.id)
                .first()
            )
            if opponent_participant is None:
                waiting_match = None
        if waiting_match is not None and opponent_participant is not None:
            opponent_tp = (
                db.query(TournamentParticipant)
                .filter_by(tournament_id=tournament.id, user_id=opponent_participant.user_id)
                .first()
            )
            if opponent_tp is not None:
                opponent_tp.status = "matched"
            participant.status = "matched"
            db.add(MatchParticipant(match_id=waiting_match.id, user_id=user.id))
            db.commit()
            register_match(db, waiting_match)
            live = arena.get(waiting_match.id)
            if live is not None:
                live.arm_waiting_timeout()
            return {"tournament_id": tournament.id, "match": _match_info(waiting_match)}

        match = _create_match(
            db,
            [user.id],
            tournament.allowed_letters,
            tournament.skills,
            "tournament",
            tournament_id=tournament.id,
            start_delay_seconds=0,
            end_mode=configs.CHALLENGE_END_MODE_ROUNDS,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        abort(409, description="Already joined")
    register_match(db, match)
    live = arena.get(match.id)
    if live is not None:
        live.arm_waiting_timeout()
    return {"tournament_id": tournament.id, "match": _match_info(match)}


@router.post("/tournaments/join")
def join_tournament_by_key():
    db = g.db
    begin_immediate(db)
    user = require_user()
    payload = body()
    try:
        key = clean_key(payload.get("key", ""))
    except ValueError as exc:
        abort(400, description=str(exc))
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
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        abort(404, description="Tournament not found")
    existing = (
        db.query(TournamentParticipant)
        .filter_by(tournament_id=tournament.id, user_id=user.id)
        .first()
    )
    if tournament.requires_key and existing is None:
        try:
            key = clean_key(payload.get("key", ""))
        except ValueError as exc:
            abort(400, description=str(exc))
        if tournament.key != key:
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


def _rematch_context(db, match_id: int, user: User):
    match = db.get(Match, match_id)
    if match is None:
        abort(404, description="Match not found")
    if match.mode != configs.CHALLENGE_MODE:
        abort(403, description="Rematches are only available for challenges")
    if match.status != "finished":
        abort(409, description="The match is not over yet")
    participant_ids = [
        row.user_id
        for row in db.query(MatchParticipant)
        .filter(MatchParticipant.match_id == match_id)
        .all()
    ]
    if user.id not in participant_ids or len(participant_ids) != 2:
        abort(403, description="You are not in this challenge")
    opponent_id = next(uid for uid in participant_ids if uid != user.id)
    offer = (
        db.query(RematchOffer)
        .filter(
            RematchOffer.match_id == match_id,
            ((RematchOffer.from_id == user.id) & (RematchOffer.to_id == opponent_id))
            | ((RematchOffer.from_id == opponent_id) & (RematchOffer.to_id == user.id)),
        )
        .order_by(RematchOffer.id.desc())
        .first()
    )
    return match, opponent_id, offer


def _expire_rematch(db, offer: RematchOffer | None) -> bool:
    if offer is None or offer.status != configs.REMATCH_STATUS_PENDING:
        return False
    expires = offer.expires_at.replace(tzinfo=UTC) if offer.expires_at else None
    if expires and expires > datetime.now(UTC):
        return False
    offer.status = configs.REMATCH_STATUS_EXPIRED
    offer.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return True


@router.get("/matches/<int:match_id>/rematch")
def get_rematch(match_id: int):
    db = g.db
    user = require_user()
    match, _opponent_id, offer = _rematch_context(db, match_id, user)
    _expire_rematch(db, offer)
    return jsonify({
        "mode": match.mode,
        "offer": _rematch_json(db, offer, user.id) if offer else None,
    })


@router.post("/matches/<int:match_id>/rematch")
def offer_rematch(match_id: int):
    db = g.db
    begin_immediate(db)
    user = require_user()
    _match, opponent_id, offer = _rematch_context(db, match_id, user)
    if offer and offer.status == configs.REMATCH_STATUS_ACCEPTED:
        abort(409, description="A rematch has already been created")
    if offer and offer.status == configs.REMATCH_STATUS_PENDING:
        return jsonify(_rematch_json(db, offer, user.id))

    if offer is None:
        offer = RematchOffer(match_id=match_id, from_id=user.id, to_id=opponent_id)
        db.add(offer)
    else:
        offer.from_id = user.id
        offer.to_id = opponent_id
        offer.expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=configs.REMATCH_TTL_HOURS)
    offer.status = configs.REMATCH_STATUS_PENDING
    offer.new_match_id = None
    offer.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.flush()
    _notify(
        db,
        opponent_id,
        configs.NOTIFICATION_REMATCH_OFFERED,
        f"{user.username} wants a rematch",
        f"/playing/{match_id}",
        {"match_id": match_id, "offer_id": offer.id},
    )
    db.commit()
    return jsonify(_rematch_json(db, offer, user.id)), 201


@router.post("/matches/<int:match_id>/rematch/accept")
def accept_rematch(match_id: int):
    db = g.db
    begin_immediate(db)
    user = require_user()
    match, _opponent_id, offer = _rematch_context(db, match_id, user)
    if offer is None:
        abort(404, description="No rematch offer found")
    if offer.to_id != user.id:
        abort(403, description="This rematch is not for you")
    if offer.status != configs.REMATCH_STATUS_PENDING:
        abort(409, description="Rematch offer is no longer pending")
    if _expire_rematch(db, offer):
        abort(410, description="Rematch offer expired")
    if offer.new_match_id and db.get(Match, offer.new_match_id) is not None:
        abort(409, description="Rematch already created")

    new_match = _create_match(
        db,
        [offer.from_id, offer.to_id],
        match.allowed_letters,
        match.skills,
        configs.CHALLENGE_MODE,
        start_delay_seconds=match.start_delay_seconds,
        end_mode=match.end_mode,
    )
    offer.status = configs.REMATCH_STATUS_ACCEPTED
    offer.new_match_id = new_match.id
    offer.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.flush()
    _notify(
        db,
        offer.from_id,
        configs.NOTIFICATION_REMATCH_ACCEPTED,
        f"{user.username} accepted your rematch",
        f"/playing/{new_match.id}",
        {"match_id": new_match.id, "offer_id": offer.id},
    )
    db.commit()
    register_match(db, new_match)
    return jsonify({
        **_rematch_json(db, offer, user.id),
        "match": _match_info(new_match),
    })


@router.post("/matches/<int:match_id>/rematch/decline")
def decline_rematch(match_id: int):
    db = g.db
    begin_immediate(db)
    user = require_user()
    _match, _opponent_id, offer = _rematch_context(db, match_id, user)
    if offer is None:
        abort(404, description="No rematch offer found")
    if offer.to_id != user.id:
        abort(403, description="This rematch is not for you")
    if offer.status != configs.REMATCH_STATUS_PENDING:
        abort(409, description="Rematch offer is no longer pending")
    if _expire_rematch(db, offer):
        abort(410, description="Rematch offer expired")
    offer.status = configs.REMATCH_STATUS_DECLINED
    offer.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.flush()
    _notify(
        db,
        offer.from_id,
        configs.NOTIFICATION_REMATCH_DECLINED,
        f"{user.username} declined your rematch",
        f"/playing/{match_id}",
        {"match_id": match_id, "offer_id": offer.id},
    )
    db.commit()
    return jsonify(_rematch_json(db, offer, user.id))


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
    users = (
        db.query(User)
        .filter(User.status == "active")
        .order_by(User.lifetime_learning_points.desc(), User.wins.desc(), User.username)
        .limit(configs.LEADERBOARD_LIMIT)
        .all()
    )
    return jsonify([
        {
            "rank": index + 1,
            "id": user.id,
            "username": user.username,
            "points": user.lifetime_learning_points,
            "wins": user.wins,
            "losses": user.losses,
            "tournaments_played": user.tournaments_played,
            "medal": index < configs.MEDAL_SLOTS,
            "avatar": avatar_info(user),
            "profile_url": f"/player/{user.id}",
        }
        for index, user in enumerate(users)
    ])


@router.get("/players/<int:user_id>")
def player_profile(user_id: int):
    """Public profile used by the leaderboard and the players list."""
    db = g.db
    user = db.query(User).filter(User.id == user_id, User.status == "active").first()
    if user is None:
        abort(404, description="Player not found")
    viewer = current_user()
    return jsonify({
        **public_profile(user),
        "friend_status": _friend_status(db, viewer.id if viewer else None, user.id),
    })


@router.get("/notifications")
def notifications():
    db = g.db
    user = require_user()
    entries = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.id.desc())
        .limit(configs.NOTIFICATIONS_LIMIT)
        .all()
    )
    unread = db.query(func.count(Notification.id)).filter(
        Notification.user_id == user.id, Notification.read.is_(False)
    ).scalar()
    return jsonify({"items": [_notification_json(entry) for entry in entries], "unread_count": unread})


@router.post("/notifications/read")
def read_notifications():
    db = g.db
    user = require_user()
    (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read.is_(False))
        .update({Notification.read: True}, synchronize_session=False)
    )
    db.commit()
    return jsonify({"ok": True, "unread_count": 0})


@router.post("/notifications/<int:entry_id>/read")
def read_notification(entry_id: int):
    db = g.db
    user = require_user()
    entry = db.get(Notification, entry_id)
    if entry is None or entry.user_id != user.id:
        abort(404, description="Notification not found")
    entry.read = True
    db.commit()
    return jsonify(_notification_json(entry))


@router.post("/words/validate")
def validate_word():
    payload = body()
    word = clean_text(payload.get("word", ""), configs.MAX_WORD_LENGTH * 2)
    letters = clean_text(payload.get("letters", ""), configs.MAX_LETTERS * 2)
    valid = is_valid_word(word, letters)
    return jsonify({"valid": valid, "points": score_word(word.strip().lower()) if valid else 0})
