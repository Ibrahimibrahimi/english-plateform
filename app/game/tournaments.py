"""Tournament creation helpers shared by the public and admin APIs.

Validation is centralised here so both entry points enforce the same bounds.
All values are passed to SQLAlchemy as bound parameters; user text is never
interpolated into a SQL string.
"""

from app import configs
from app.game.service import letters_for, new_key, skill_pool
from app.models import Tournament
from app.validation import ConflictError, clean_text, parse_int


def validate_tournament(db, payload: dict) -> dict:
    name = clean_text(
        payload.get("name", ""),
        configs.TOURNAMENT_NAME_MAX_LENGTH,
        required=True,
        label="Tournament name",
    )
    if len(name) < configs.TOURNAMENT_NAME_MIN_LENGTH:
        raise ValueError(
            f"Tournament name must be {configs.TOURNAMENT_NAME_MIN_LENGTH}-"
            f"{configs.TOURNAMENT_NAME_MAX_LENGTH} characters"
        )
    description = clean_text(
        payload.get("description", ""), configs.TOURNAMENT_DESCRIPTION_MAX_LENGTH, label="Description"
    )
    max_players = parse_int(
        payload.get("max_players"),
        minimum=configs.MIN_TOURNAMENT_PLAYERS,
        maximum=configs.MAX_TOURNAMENT_PLAYERS,
        label="max_players",
        default=configs.DEFAULT_TOURNAMENT_MAX_PLAYERS,
    )
    letters = letters_for(db, str(payload.get("allowed_letters", "all")), kind="tournament")
    skills = ",".join(skill_pool(str(payload.get("skills", ""))))
    return {
        "name": name,
        "description": description,
        "max_players": max_players,
        "allowed_letters": letters,
        "skills": skills,
    }


def create_tournament(db, admin, payload: dict) -> Tournament:
    values = validate_tournament(db, payload)
    if db.query(Tournament).filter(Tournament.name == values["name"]).first() is not None:
        raise ConflictError("Tournament name already exists")
    tournament = Tournament(key=new_key("T"), created_by=admin.id, **values)
    db.add(tournament)
    db.commit()
    return tournament
