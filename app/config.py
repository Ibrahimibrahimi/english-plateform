import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
WORDS_FILE = DATA_DIR / "words.txt"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'spellbattle.db'}")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me")
SESSION_MAX_AGE = 60 * 60 * 24 * 7
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@spellbattle.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

MIN_WORD_LENGTH = 3
MAX_WORD_LENGTH = 12
MIN_LETTERS = 6
MAX_LETTERS = 12
ROUNDS_PER_MATCH = 5
ROUND_SECONDS = 60

ARMOR_BASE = 100
ARMOR_PER_POINT = 2
ARMOR_CAP = 260
ATTACK_BASE = 6
ATTACK_PER_POINT = 1
ATTACK_CAP = 30

DRAIN_AMOUNT = 10
HEAL_COST = 10
HEAL_AMOUNT = 30
HEAL_COOLDOWN = 15

SPECIAL_THRESHOLDS = {
    "drain": 15,
    "swap_points": 30,
    "swap_skill": 45,
    "clear_skill": 60,
}
SPECIAL_LABELS = {
    "drain": "Drain points",
    "swap_points": "Swap points",
    "swap_skill": "Swap skill",
    "clear_skill": "Clear skill",
}
