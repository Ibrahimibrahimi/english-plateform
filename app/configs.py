"""Single source of truth for every application setting.

Everything that can be tuned (paths, limits, game rules, validation bounds and
UI options) lives here so it can be reviewed and changed in one place.
Environment variables are still honoured for deployment-specific values.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths and deployment
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
WORDS_FILE = DATA_DIR / "words.txt"
UPLOAD_DIR = STATIC_DIR / "uploads"
UPLOAD_URL_PREFIX = "/static/uploads"
AVATAR_UPLOAD_MAX_BYTES = 2 * 1024 * 1024
AVATAR_UPLOAD_EXTENSIONS = ("png", "jpg", "jpeg", "gif", "webp")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'spellbattle.db'}")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me")
DEV_SECRET_KEY = "dev-only-secret-change-me"
SESSION_MAX_AGE = 60 * 60 * 24 * 7
SESSION_COOKIE_NAME = "sb_session"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
COOKIE_SAMESITE = "Lax"
SESSION_SALT = "spellbattle-session"
MAX_REQUEST_BYTES = AVATAR_UPLOAD_MAX_BYTES + 64 * 1024
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@spellbattle.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_USERNAME = "admin"

ALLOWED_ORIGINS = tuple(
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
)
WS_PING_INTERVAL = 25
WS_MAX_MESSAGE_SIZE = int(os.getenv("WS_MAX_MESSAGE_SIZE", "4096"))
RECONNECT_GRACE_SECONDS = 30
PRESENCE_TIMEOUT_SECONDS = 30
MATCH_RETENTION_SECONDS = int(os.getenv("MATCH_RETENTION_SECONDS", "600"))

# ---------------------------------------------------------------------------
# Authentication / input validation limits
# ---------------------------------------------------------------------------
PASSWORD_HASH_ITERATIONS = 200_000
PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_SALT_BYTES = 16
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
USERNAME_PATTERN = r"^[A-Za-z0-9_.-]+$"
EMAIL_MIN_LENGTH = 5
EMAIL_MAX_LENGTH = 120
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
TOURNAMENT_NAME_MIN_LENGTH = 3
TOURNAMENT_NAME_MAX_LENGTH = 100
TOURNAMENT_DESCRIPTION_MAX_LENGTH = 300
LETTER_SET_NAME_MIN_LENGTH = 2
LETTER_SET_NAME_MAX_LENGTH = 100
KEY_MAX_LENGTH = 20
SEARCH_MAX_LENGTH = 50
EVENT_DATA_MAX_LENGTH = 500
ADMIN_ACTION_DETAIL_MAX_LENGTH = 500
NOTIFICATION_MESSAGE_MAX_LENGTH = 300

# ---------------------------------------------------------------------------
# Learning content and round rules
# ---------------------------------------------------------------------------
MIN_WORD_LENGTH = 3
MAX_WORD_LENGTH = 15
MIN_LETTERS = 6
MAX_LETTERS = 20
CHALLENGE_MIN_LETTERS = 6
CHALLENGE_MAX_LETTERS = 17
TOURNAMENT_MIN_LETTERS = 6
TOURNAMENT_MAX_LETTERS = 22
DEFAULT_LETTERS = "AEIOURSTLND"
ROUNDS_PER_MATCH = 10
ROUND_SECONDS = 120
MATCH_TICK_SECONDS = 1.0

# ---------------------------------------------------------------------------
# Tanks and resources
# ---------------------------------------------------------------------------
HEALTH_BASE = 100
HEALTH_PER_POINT = 3
HEALTH_CAP = 300
ARMOR_BASE = 100
ARMOR_PER_POINT = 2
ARMOR_CAP = 200
ATTACK_BASE = 3
ATTACK_PER_POINT = 1
ATTACK_CAP = 20 # Big attack maybe ?

HEALTH_REGEN_PERCENT = 0.20
ARMOR_REGEN_PERCENT = 0.15
REGEN_HEALTH_COST = 10
REGEN_ARMOR_COST = 10
REGEN_COOLDOWN = 10
SPECIAL_REGEN_COST = 15
SPECIAL_REGEN_COOLDOWN = 10

# ---------------------------------------------------------------------------
# Special moves
# ---------------------------------------------------------------------------
BLOCK_SECONDS = 5
REDUCE_POINTS_PERCENT = 0.20
STEAL_MIN_POINTS = 12
STEAL_MAX_POINTS = 30
SKILLS = {
    "BLOCK_POINTS": "Block point generation (5s)",
    "REDUCE_POINTS_PERCENT": "Reduce opponent points by 20%",
    "STEAL_POINTS_RANGE": "Take 12-30 points",
    "SWAP_SKILLS": "Switch skills with opponent",
    "CLEAR_OPPONENT_SKILL": "Clear opponent skill",
}
SKILL_CODES = list(SKILLS)
SKILL_ICONS = {
    "BLOCK_POINTS": "🛡️",
    "REDUCE_POINTS_PERCENT": "📉",
    "STEAL_POINTS_RANGE": "💰",
    "SWAP_SKILLS": "🔄",
    "CLEAR_OPPONENT_SKILL": "🚫",
}

# ---------------------------------------------------------------------------
# Challenges, tournaments and leaderboards
# ---------------------------------------------------------------------------
CHALLENGE_TTL_HOURS = 24
CHALLENGE_LIST_LIMIT = 50
CHALLENGE_PLAYERS = 2
CHALLENGE_DELAY_DEFAULT_SECONDS = 0
CHALLENGE_DELAY_MIN_SECONDS = 0
CHALLENGE_DELAY_MAX_SECONDS = 300
CHALLENGE_END_MODE_ROUNDS = "rounds"
CHALLENGE_END_MODE_INFINITE = "infinite"
CHALLENGE_END_MODES = (CHALLENGE_END_MODE_ROUNDS, CHALLENGE_END_MODE_INFINITE)
MIN_TOURNAMENT_PLAYERS = 2
MAX_TOURNAMENT_PLAYERS = 128
DEFAULT_TOURNAMENT_MAX_PLAYERS = 20
DEFAULT_TOURNAMENT_NAME = "SpellBattle Open"
DEFAULT_TOURNAMENT_DESCRIPTION = "The always-open tournament. Join with the key below."
DEFAULT_TOURNAMENT_STATUS = "open"
TOURNAMENT_STATUSES = (
    "draft",
    "open",
    "registration_closed",
    "in_progress",
    "completed",
    "cancelled",
)
LEADERBOARD_LIMIT = 50
MEDAL_SLOTS = 3

# ---------------------------------------------------------------------------
# Profiles and avatars
# ---------------------------------------------------------------------------
DEFAULT_AVATAR = "default"
AVATARS = {
    "default": {"label": "Tank", "emoji": "🎮", "color": "#f59e0b"},
    "fox": {"label": "Fox", "emoji": "🦊", "color": "#f97316"},
    "owl": {"label": "Owl", "emoji": "🦉", "color": "#8b5cf6"},
    "lion": {"label": "Lion", "emoji": "🦁", "color": "#eab308"},
    "cat": {"label": "Cat", "emoji": "🐱", "color": "#ec4899"},
    "robot": {"label": "Robot", "emoji": "🤖", "color": "#06b6d4"},
    "rocket": {"label": "Rocket", "emoji": "🚀", "color": "#3b82f6"},
    "crown": {"label": "Crown", "emoji": "👑", "color": "#d4af37"},
}

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
NOTIFICATIONS_LIMIT = 30
NOTIFICATION_CHALLENGE_RECEIVED = "challenge.received"
NOTIFICATION_CHALLENGE_JOINED = "challenge.joined"
NOTIFICATION_FRIEND_REQUEST_RECEIVED = "friend.request_received"
NOTIFICATION_FRIEND_REQUEST_ACCEPTED = "friend.request_accepted"
NOTIFICATION_FRIEND_REQUEST_DECLINED = "friend.request_declined"
NOTIFICATION_REMATCH_OFFERED = "rematch.offered"
NOTIFICATION_REMATCH_ACCEPTED = "rematch.accepted"
NOTIFICATION_REMATCH_DECLINED = "rematch.declined"
NOTIFICATION_TYPES = (
    NOTIFICATION_CHALLENGE_RECEIVED,
    NOTIFICATION_CHALLENGE_JOINED,
    NOTIFICATION_FRIEND_REQUEST_RECEIVED,
    NOTIFICATION_FRIEND_REQUEST_ACCEPTED,
    NOTIFICATION_FRIEND_REQUEST_DECLINED,
    NOTIFICATION_REMATCH_OFFERED,
    NOTIFICATION_REMATCH_ACCEPTED,
    NOTIFICATION_REMATCH_DECLINED,
)

# ---------------------------------------------------------------------------
# Friends and rematches
# ---------------------------------------------------------------------------
FRIEND_STATUS_PENDING = "pending"
FRIEND_STATUS_ACCEPTED = "accepted"
FRIEND_STATUS_DECLINED = "declined"
REMATCH_STATUS_PENDING = "pending"
REMATCH_STATUS_ACCEPTED = "accepted"
REMATCH_STATUS_DECLINED = "declined"
REMATCH_STATUS_EXPIRED = "expired"
REMATCH_TTL_HOURS = 24
CHALLENGE_MODE = "challenge"
TOURNAMENT_MODE = "tournament"
