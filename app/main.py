from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config
from app.auth import COOKIE_NAME, hash_password, read_token
from app.db import SessionLocal, init_db
from app.game.presence import touch
from app.models import LetterSet, User
from app.routers import admin, api, auth, pages, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    yield


app = FastAPI(title="SpellBattle", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.middleware("http")
async def presence_middleware(request, call_next):
    user_id = read_token(request.cookies.get(COOKIE_NAME))
    if user_id is not None:
        touch(user_id)
    return await call_next(request)


app.include_router(auth.router)
app.include_router(api.router)
app.include_router(admin.router)
app.include_router(ws.router)
app.include_router(pages.router)
