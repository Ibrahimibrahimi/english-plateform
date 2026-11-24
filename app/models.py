from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="player")
    points_total: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    key: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LetterSet(Base):
    __tablename__ = "letter_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    letters: Mapped[str] = mapped_column(String(30))
    tournament_id: Mapped[int | None] = mapped_column(ForeignKey("tournaments.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), default="friend")
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    tournament_id: Mapped[int | None] = mapped_column(ForeignKey("tournaments.id"), nullable=True)
    round_index: Mapped[int] = mapped_column(Integer, default=0)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MatchPlayer(Base):
    __tablename__ = "match_players"
    __table_args__ = (UniqueConstraint("match_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    points: Mapped[int] = mapped_column(Integer, default=0)
    armor: Mapped[int] = mapped_column(Integer, default=100)
    max_armor: Mapped[int] = mapped_column(Integer, default=100)
    attack: Mapped[int] = mapped_column(Integer, default=6)
    used_specials: Mapped[str] = mapped_column(String(200), default="")


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    index: Mapped[int] = mapped_column(Integer)
    letters: Mapped[str] = mapped_column(String(30))
    duration_seconds: Mapped[int] = mapped_column(Integer, default=60)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("round_id", "user_id", "word"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"))
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    word: Mapped[str] = mapped_column(String(30))
    points: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
