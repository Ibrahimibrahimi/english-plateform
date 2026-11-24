import random
import time

from app import config


def score_word(word: str) -> int:
    length = len(word.strip().lower())
    return max(0, length * (length - 1) // 2)


def stats_for_points(points: int) -> dict[str, int]:
    points = max(0, points)
    return {
        "max_health": min(config.HEALTH_CAP, config.HEALTH_BASE + points * config.HEALTH_PER_POINT),
        "max_armor": min(config.ARMOR_CAP, config.ARMOR_BASE + points * config.ARMOR_PER_POINT),
        "attack": min(config.ATTACK_CAP, config.ATTACK_BASE + points * config.ATTACK_PER_POINT),
    }


def new_player(user_id: int, username: str, skill_pool: list[str]) -> dict:
    player = {
        "user_id": user_id,
        "username": username,
        "points": 0,
        "health": config.HEALTH_BASE,
        "max_health": config.HEALTH_BASE,
        "armor": config.ARMOR_BASE,
        "max_armor": config.ARMOR_BASE,
        "attack": config.ATTACK_BASE,
        "skill": None,
        "blocked_until": 0.0,
        "health_ready_at": 0.0,
        "armor_ready_at": 0.0,
        "skill_ready_at": 0.0,
        "connected": True,
    }
    if skill_pool:
        player["skill"] = random.choice(skill_pool)
    sync_player(player, skill_pool)
    return player


def sync_player(player: dict, skill_pool: list[str]) -> None:
    stats = stats_for_points(player["points"])
    player["max_health"] = stats["max_health"]
    player["max_armor"] = stats["max_armor"]
    player["attack"] = stats["attack"]
    player["health"] = max(0, min(player["health"], stats["max_health"]))
    player["armor"] = max(0, min(player["armor"], stats["max_armor"]))
    if player["skill"] is not None and player["skill"] not in skill_pool:
        player["skill"] = None


def is_blocked(player: dict, now: float | None = None) -> bool:
    return (now if now is not None else time.monotonic()) < player["blocked_until"]


def apply_damage(actor: dict, opponent: dict) -> None:
    damage = actor["attack"]
    absorbed = min(opponent["armor"], damage)
    opponent["armor"] -= absorbed
    opponent["health"] = max(0, opponent["health"] - (damage - absorbed))


def regenerate_health(player: dict, now: float | None = None) -> str:
    now = time.monotonic() if now is None else now
    if player["points"] < config.REGEN_HEALTH_COST:
        raise ValueError(f"health regeneration costs {config.REGEN_HEALTH_COST} points")
    if now < player["health_ready_at"]:
        raise ValueError("health regeneration is on cooldown")
    amount = round(player["max_health"] * config.HEALTH_REGEN_PERCENT)
    player["points"] -= config.REGEN_HEALTH_COST
    player["health"] = min(player["max_health"], player["health"] + amount)
    player["health_ready_at"] = now + config.REGEN_COOLDOWN
    return f"Restored {amount} health"


def regenerate_armor(player: dict, now: float | None = None) -> str:
    now = time.monotonic() if now is None else now
    if player["points"] < config.REGEN_ARMOR_COST:
        raise ValueError(f"armor regeneration costs {config.REGEN_ARMOR_COST} points")
    if now < player["armor_ready_at"]:
        raise ValueError("armor regeneration is on cooldown")
    amount = round(player["max_armor"] * config.ARMOR_REGEN_PERCENT)
    player["points"] -= config.REGEN_ARMOR_COST
    player["armor"] = min(player["max_armor"], player["armor"] + amount)
    player["armor_ready_at"] = now + config.REGEN_COOLDOWN
    return f"Restored {amount} armor"


def regenerate_skill(player: dict, skill_pool: list[str], now: float | None = None) -> str:
    now = time.monotonic() if now is None else now
    if not skill_pool:
        raise ValueError("no skills are available")
    if player["points"] < config.SPECIAL_REGEN_COST:
        raise ValueError(f"skill regeneration costs {config.SPECIAL_REGEN_COST} points")
    if now < player["skill_ready_at"]:
        raise ValueError("skill regeneration is on cooldown")
    player["points"] -= config.SPECIAL_REGEN_COST
    player["skill"] = random.choice(skill_pool)
    player["skill_ready_at"] = now + config.SPECIAL_REGEN_COOLDOWN
    sync_player(player, skill_pool)
    return f"New skill: {config.SKILLS[player['skill']]}"


def activate_skill(actor: dict, opponent: dict, skill_pool: list[str], now: float | None = None) -> str:
    now = time.monotonic() if now is None else now
    skill = actor["skill"]
    if skill is None or skill not in skill_pool:
        raise ValueError("no skill available")
    if is_blocked(actor, now):
        raise ValueError("your skills are blocked")

    actor["skill"] = None
    if skill == "BLOCK_POINTS":
        opponent["blocked_until"] = now + config.BLOCK_SECONDS
        detail = f"Point generation blocked for {config.BLOCK_SECONDS}s"
    elif skill == "REDUCE_POINTS_PERCENT":
        reduction = round(opponent["points"] * config.REDUCE_POINTS_PERCENT)
        opponent["points"] = max(0, opponent["points"] - reduction)
        detail = f"Reduced opponent points by {reduction}"
    elif skill == "STEAL_POINTS_RANGE":
        maximum = min(config.STEAL_MAX_POINTS, opponent["points"])
        amount = random.randint(min(config.STEAL_MIN_POINTS, maximum), maximum) if maximum else 0
        opponent["points"] -= amount
        actor["points"] += amount
        detail = f"Stole {amount} points"
    elif skill == "SWAP_SKILLS":
        actor["skill"], opponent["skill"] = opponent["skill"], actor["skill"]
        detail = "Skills switched"
    elif skill == "CLEAR_OPPONENT_SKILL":
        opponent["skill"] = None
        detail = "Opponent skill cleared"
    else:
        raise ValueError("unknown skill")

    for player in (actor, opponent):
        sync_player(player, skill_pool)
    return detail
