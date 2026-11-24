import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db import get_db
from app.game.words import normalize_letters
from app.models import AdminAction, LetterSet, Tournament

router = APIRouter(prefix="/admin/api", tags=["admin"])


class LetterSetIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    letters: str


class StatusIn(BaseModel):
    status: str = Field(pattern="^(draft|open|registration_closed|in_progress|completed|cancelled)$")


def log(db: Session, admin_id: int, action: str, detail: dict) -> None:
    db.add(AdminAction(admin_id=admin_id, action=action, detail=json.dumps(detail)[:500]))


@router.get("/letter-sets")
def letter_sets(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    return [
        {"id": entry.id, "name": entry.name, "letters": entry.letters}
        for entry in db.query(LetterSet).order_by(LetterSet.id).all()
    ]


@router.post("/letter-sets")
def create_letter_set(payload: LetterSetIn, request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request)
    try:
        letters = normalize_letters(payload.letters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    entry = LetterSet(name=payload.name.strip(), letters=letters, created_by=admin.id)
    db.add(entry)
    log(db, admin.id, "letter_set.created", {"name": entry.name, "letters": letters})
    db.commit()
    return {"id": entry.id, "name": entry.name, "letters": entry.letters}


@router.delete("/letter-sets/{entry_id}")
def delete_letter_set(entry_id: int, request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request)
    entry = db.get(LetterSet, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Letter set not found")
    db.delete(entry)
    log(db, admin.id, "letter_set.deleted", {"id": entry_id})
    db.commit()
    return {"ok": True}


@router.get("/tournaments")
def tournaments(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    return [
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
    ]


@router.post("/tournaments/{tournament_id}/status")
def set_tournament_status(tournament_id: int, payload: StatusIn, request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request)
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="Tournament not found")
    tournament.status = payload.status
    log(db, admin.id, "tournament.status", {"id": tournament_id, "status": payload.status})
    db.commit()
    return {"id": tournament_id, "status": tournament.status}


@router.get("/actions")
def actions(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    return [
        {"id": entry.id, "admin_id": entry.admin_id, "action": entry.action, "detail": entry.detail, "created_at": entry.created_at}
        for entry in db.query(AdminAction).order_by(AdminAction.id.desc()).limit(100).all()
    ]
