from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from app import config
from app.auth import COOKIE_NAME, current_user, hash_password, read_token
from app.db import SessionLocal, init_db
from app.game.presence import touch
from app.game.service import reconcile_matches
from app.models import LetterSet, User
from app.routers import admin, api, auth, pages, ws


def _seed():
    init_db()
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.role == "admin").first()
        if admin_user is None:
            admin_user = User(
                username="admin",
                email=config.ADMIN_EMAIL.lower(),
                password_hash=hash_password(config.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin_user)
            db.commit()
        if db.query(LetterSet).count() == 0:
            db.add(LetterSet(name="Starter letters", letters="AEIOURSTLND", created_by=admin_user.id))
            db.commit()
    finally:
        db.close()


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(config.STATIC_DIR), template_folder=str(config.TEMPLATES_DIR))
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
        MAX_CONTENT_LENGTH=1024 * 1024,
        SOCK_SERVER_OPTIONS={"ping_interval": 25, "max_message_size": config.WS_MAX_MESSAGE_SIZE},
    )
    if config.SECRET_KEY == "dev-only-secret-change-me":
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
