from datetime import UTC, datetime, timedelta

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app import configs
from app.db import Base


def utcnow():
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="player")
    status: Mapped[str] = mapped_column(String(20), default="active")
    lifetime_learning_points: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    tournaments_played: Mapped[int] = mapped_column(Integer, default=0)
    avatar: Mapped[str] = mapped_column(String(20), default=configs.DEFAULT_AVATAR)
    avatar_image: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(String(300))
    link: Mapped[str] = mapped_column(String(300), default="")
    data: Mapped[str] = mapped_column(String(500), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FriendRequest(Base):
    __tablename__ = "friend_requests"
    __table_args__ = (UniqueConstraint("from_id", "to_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    from_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    to_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=configs.FRIEND_STATUS_PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    key: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    max_players: Mapped[int] = mapped_column(Integer, default=configs.DEFAULT_TOURNAMENT_MAX_PLAYERS)
    allowed_letters: Mapped[str] = mapped_column(String(30), default="all")
    skills: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"
    __table_args__ = (UniqueConstraint("tournament_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="active")


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    opponent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    allowed_letters: Mapped[str] = mapped_column(String(30), default="all")
    skills: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="created")
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: utcnow() + timedelta(hours=configs.CHALLENGE_TTL_HOURS)
    )
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), default="challenge")
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    tournament_id: Mapped[int | None] = mapped_column(ForeignKey("tournaments.id"), nullable=True)
    challenge_id: Mapped[int | None] = mapped_column(ForeignKey("challenges.id"), nullable=True)
    allowed_letters: Mapped[str] = mapped_column(String(30), default="all")
    skills: Mapped[str] = mapped_column(String(300), default="")
    round_index: Mapped[int] = mapped_column(Integer, default=0)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MatchParticipant(Base):
    __tablename__ = "match_participants"
    __table_args__ = (UniqueConstraint("match_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    points: Mapped[int] = mapped_column(Integer, default=0)
    health: Mapped[int] = mapped_column(Integer, default=configs.HEALTH_BASE)
    max_health: Mapped[int] = mapped_column(Integer, default=configs.HEALTH_BASE)
    armor: Mapped[int] = mapped_column(Integer, default=configs.ARMOR_BASE)
    max_armor: Mapped[int] = mapped_column(Integer, default=configs.ARMOR_BASE)
    attack: Mapped[int] = mapped_column(Integer, default=configs.ATTACK_BASE)
    skill: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")


class RematchOffer(Base):
    __tablename__ = "rematch_offers"
    __table_args__ = (UniqueConstraint("match_id", "from_id", "to_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    from_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    to_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=configs.REMATCH_STATUS_PENDING)
    new_match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: utcnow() + timedelta(hours=configs.REMATCH_TTL_HOURS)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LetterSet(Base):
    __tablename__ = "letter_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    letters: Mapped[str] = mapped_column(String(30))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    index: Mapped[int] = mapped_column(Integer)
    letters: Mapped[str] = mapped_column(String(30))
    duration_seconds: Mapped[int] = mapped_column(Integer, default=configs.ROUND_SECONDS)
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
    blocked: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MatchEvent(Base):
    __tablename__ = "match_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    event: Mapped[str] = mapped_column(String(40))
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AdminAction(Base):
    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
