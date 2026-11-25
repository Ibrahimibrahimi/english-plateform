import json

from flask import Blueprint, abort, g, jsonify, request

from app.auth import require_admin
from app.game.words import normalize_letters
from app.models import AdminAction, LetterSet, Tournament

router = Blueprint("admin", __name__, url_prefix="/admin/api")


def log(db, admin_id: int, action: str, detail: dict) -> None:
    db.add(AdminAction(admin_id=admin_id, action=action, detail=json.dumps(detail)[:500]))


@router.get("/letter-sets")
def letter_sets():
    db = g.db
    require_admin()
    return jsonify([
        {"id": entry.id, "name": entry.name, "letters": entry.letters}
        for entry in db.query(LetterSet).order_by(LetterSet.id).all()
    ])


@router.post("/letter-sets")
def create_letter_set():
    db = g.db
    admin = require_admin()
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if len(name) < 2:
        abort(400, description="Name must be at least 2 characters")
    try:
        letters = normalize_letters(str(payload.get("letters", "")))
    except ValueError as exc:
        abort(400, description=str(exc))
    entry = LetterSet(name=name, letters=letters, created_by=admin.id)
    db.add(entry)
    log(db, admin.id, "letter_set.created", {"name": entry.name, "letters": letters})
    db.commit()
    return jsonify({"id": entry.id, "name": entry.name, "letters": entry.letters})


@router.delete("/letter-sets/<int:entry_id>")
def delete_letter_set(entry_id: int):
    db = g.db
    admin = require_admin()
    entry = db.get(LetterSet, entry_id)
    if entry is None:
        abort(404, description="Letter set not found")
    db.delete(entry)
    log(db, admin.id, "letter_set.deleted", {"id": entry_id})
    db.commit()
    return jsonify({"ok": True})


@router.get("/tournaments")
def tournaments():
    db = g.db
    require_admin()
    return jsonify([
        {
            "id": tournament.id,
            "name": tournament.name,
            "key": tournament.key,
            "status": tournament.status,
            "max_players": tournament.max_players,
            "allowed_letters": tournament.allowed_letters,
            "skills": tournament.skills,
        }
        for tournament in db.query(Tournament).order_by(Tournament.id).all()
    ])


@router.post("/tournaments/<int:tournament_id>/status")
def set_tournament_status(tournament_id: int):
    db = g.db
    admin = require_admin()
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status", ""))
    if status not in {"draft", "open", "registration_closed", "in_progress", "completed", "cancelled"}:
        abort(400, description="Invalid status")
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        abort(404, description="Tournament not found")
    tournament.status = status
    log(db, admin.id, "tournament.status", {"id": tournament_id, "status": status})
    db.commit()
    return jsonify({"id": tournament_id, "status": tournament.status})


@router.get("/actions")
def actions():
    db = g.db
    require_admin()
    return jsonify([
        {
            "id": entry.id,
            "admin_id": entry.admin_id,
            "action": entry.action,
            "detail": entry.detail,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in db.query(AdminAction).order_by(AdminAction.id.desc()).limit(100).all()
    ])
