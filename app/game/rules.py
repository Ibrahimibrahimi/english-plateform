import random
import time

from app import configs


def score_word(word: str) -> int:
    length = len(word.strip().lower())
    return max(0, length * (length - 1) // 2)


def stats_for_points(points: int) -> dict[str, int]:
    points = max(0, points)
    return {
        "max_health": min(configs.HEALTH_CAP, configs.HEALTH_BASE + points * configs.HEALTH_PER_POINT),
        "max_armor": min(configs.ARMOR_CAP, configs.ARMOR_BASE + points * configs.ARMOR_PER_POINT),
        "attack": min(configs.ATTACK_CAP, configs.ATTACK_BASE + points * configs.ATTACK_PER_POINT),
    }


def new_player(user_id: int, username: str, skill_pool: list[str]) -> dict:
    player = {
        "user_id": user_id,
        "username": username,
        "points": 0,
        "health": configs.HEALTH_BASE,
        "max_health": configs.HEALTH_BASE,
        "armor": configs.ARMOR_BASE,
        "max_armor": configs.ARMOR_BASE,
        "attack": configs.ATTACK_BASE,
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
    if player["points"] < configs.REGEN_HEALTH_COST:
        raise ValueError(f"health regeneration costs {configs.REGEN_HEALTH_COST} points")
    if now < player["health_ready_at"]:
        raise ValueError("health regeneration is on cooldown")
    amount = round(player["max_health"] * configs.HEALTH_REGEN_PERCENT)
    player["points"] -= configs.REGEN_HEALTH_COST
    player["health"] = min(player["max_health"], player["health"] + amount)
    player["health_ready_at"] = now + configs.REGEN_COOLDOWN
    return f"Restored {amount} health"


def regenerate_armor(player: dict, now: float | None = None) -> str:
    now = time.monotonic() if now is None else now
    if player["points"] < configs.REGEN_ARMOR_COST:
        raise ValueError(f"armor regeneration costs {configs.REGEN_ARMOR_COST} points")
    if now < player["armor_ready_at"]:
        raise ValueError("armor regeneration is on cooldown")
    amount = round(player["max_armor"] * configs.ARMOR_REGEN_PERCENT)
    player["points"] -= configs.REGEN_ARMOR_COST
    player["armor"] = min(player["max_armor"], player["armor"] + amount)
    player["armor_ready_at"] = now + configs.REGEN_COOLDOWN
    return f"Restored {amount} armor"


def regenerate_skill(player: dict, skill_pool: list[str], now: float | None = None) -> str:
    now = time.monotonic() if now is None else now
    if not skill_pool:
        raise ValueError("no skills are available")
    if player["points"] < configs.SPECIAL_REGEN_COST:
        raise ValueError(f"skill regeneration costs {configs.SPECIAL_REGEN_COST} points")
    if now < player["skill_ready_at"]:
        raise ValueError("skill regeneration is on cooldown")
    player["points"] -= configs.SPECIAL_REGEN_COST
    player["skill"] = random.choice(skill_pool)
    player["skill_ready_at"] = now + configs.SPECIAL_REGEN_COOLDOWN
    sync_player(player, skill_pool)
    return f"New skill: {configs.SKILLS[player['skill']]}"


def activate_skill(actor: dict, opponent: dict, skill_pool: list[str], now: float | None = None) -> str:
    now = time.monotonic() if now is None else now
    skill = actor["skill"]
    if skill is None or skill not in skill_pool:
        raise ValueError("no skill available")
    if is_blocked(actor, now):
        raise ValueError("your skills are blocked")

    actor["skill"] = None
    if skill == "BLOCK_POINTS":
        opponent["blocked_until"] = now + configs.BLOCK_SECONDS
        detail = f"Point generation blocked for {configs.BLOCK_SECONDS}s"
    elif skill == "REDUCE_POINTS_PERCENT":
        reduction = round(opponent["points"] * configs.REDUCE_POINTS_PERCENT)
        opponent["points"] = max(0, opponent["points"] - reduction)
        detail = f"Reduced opponent points by {reduction}"
    elif skill == "STEAL_POINTS_RANGE":
        maximum = min(configs.STEAL_MAX_POINTS, opponent["points"])
        amount = random.randint(min(configs.STEAL_MIN_POINTS, maximum), maximum) if maximum else 0
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
