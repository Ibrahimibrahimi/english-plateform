from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from app import configs
from app.auth import COOKIE_NAME, current_user, hash_password, read_token
from app.db import SessionLocal, ensure_column, init_db
from app.game.presence import touch
from app.game.service import new_key, reconcile_matches
from app.models import LetterSet, Tournament, User
from app.routers import admin, api, auth, pages, ws
from app.validation import ConflictError


def _seed():
    init_db()
    # Keep databases created by older versions working after new settings were added.
    ensure_column("users", "avatar", "VARCHAR(20)", f"'{configs.DEFAULT_AVATAR}'")
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.role == "admin").first()
        if admin_user is None:
            admin_user = User(
                username=configs.ADMIN_USERNAME,
                email=configs.ADMIN_EMAIL.lower(),
                password_hash=hash_password(configs.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin_user)
            db.flush()
        if db.query(LetterSet).count() == 0:
            db.add(LetterSet(name="Starter letters", letters=configs.DEFAULT_LETTERS, created_by=admin_user.id))
        # A default, always-available tournament must exist from the first boot.
        if db.query(Tournament).filter(Tournament.name == configs.DEFAULT_TOURNAMENT_NAME).first() is None:
            db.add(
                Tournament(
                    name=configs.DEFAULT_TOURNAMENT_NAME,
                    description=configs.DEFAULT_TOURNAMENT_DESCRIPTION,
                    key=new_key("T"),
                    max_players=configs.DEFAULT_TOURNAMENT_MAX_PLAYERS,
                    allowed_letters=configs.DEFAULT_LETTERS,
                    skills=",".join(configs.SKILL_CODES),
                    status=configs.DEFAULT_TOURNAMENT_STATUS,
                    created_by=admin_user.id,
                )
            )
        db.commit()
    finally:
        db.close()


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(configs.STATIC_DIR), template_folder=str(configs.TEMPLATES_DIR))
    app.config.update(
        SECRET_KEY=configs.SECRET_KEY,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=configs.COOKIE_SAMESITE,
        SESSION_COOKIE_SECURE=configs.SESSION_COOKIE_SECURE,
        MAX_CONTENT_LENGTH=configs.MAX_REQUEST_BYTES,
        SOCK_SERVER_OPTIONS={
            "ping_interval": configs.WS_PING_INTERVAL,
            "max_message_size": configs.WS_MAX_MESSAGE_SIZE,
        },
    )
    if configs.SECRET_KEY == configs.DEV_SECRET_KEY:
        app.logger.warning("Using the development SECRET_KEY; set SECRET_KEY before deploying")

    _seed()
    reconcile_matches()

    @app.before_request
    def load_user():
        g.current_user = None
        g.db = None
        if request.path.startswith(("/ws/", "/static/")):
            return
        g.db = SessionLocal()
        user_id = read_token(request.cookies.get(COOKIE_NAME))
        if user_id is not None:
            g.current_user = current_user()
            if g.current_user is not None:
                touch(user_id)

    @app.teardown_request
    def close_db(_exc=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        detail = exc.description or exc.name
        return jsonify({"detail": detail}), exc.code

    @app.errorhandler(ConflictError)
    def handle_conflict(exc):
        return jsonify({"detail": str(exc)}), 409

    @app.errorhandler(ValueError)
    def handle_value_error(exc):
        return jsonify({"detail": str(exc)}), 400

    app.register_blueprint(pages.router)
    app.register_blueprint(auth.router)
    app.register_blueprint(api.router)
    app.register_blueprint(admin.router)
    ws.register(app)
    return app


app = create_app()
