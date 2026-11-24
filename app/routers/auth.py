from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    clear_session,
    hash_password,
    public_user,
    require_user,
    set_session,
    verify_password,
)
from app.db import get_db
from app.game.presence import touch
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/signup")
def signup(payload: SignupIn, response: Response, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    username = payload.username.strip()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    user = User(username=username, email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    set_session(response, user.id)
    touch(user.id)
    return public_user(user)


@router.post("/login")
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")
    set_session(response, user.id)
    touch(user.id)
    return public_user(user)


@router.post("/logout")
def logout(response: Response):
    clear_session(response)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = require_user(request)
    touch(user.id)
    return public_user(user)
