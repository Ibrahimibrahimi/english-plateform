import time

from app import config


def score_word(word: str) -> int:
    length = len(word.strip().lower())
    return max(0, length * (length - 1) // 2)


def stats_for_points(points: int) -> dict[str, int]:
    return {
        "max_armor": min(config.ARMOR_CAP, config.ARMOR_BASE + max(0, points) * config.ARMOR_PER_POINT),
        "attack": min(config.ATTACK_CAP, config.ATTACK_BASE + max(0, points) * config.ATTACK_PER_POINT),
    }


def unlocked_specials(points: int) -> list[str]:
    return [name for name, threshold in config.SPECIAL_THRESHOLDS.items() if points >= threshold]


def new_player(user_id: int, username: str) -> dict:
    return {
        "user_id": user_id,
        "username": username,
        "points": 0,
        "armor": config.ARMOR_BASE,
        "max_armor": config.ARMOR_BASE,
        "attack": config.ATTACK_BASE,
        "specials": [],
        "used_specials": [],
        "equipped": None,
        "last_heal": 0.0,
    }


def sync_player(player: dict) -> None:
    stats = stats_for_points(player["points"])
    player["max_armor"] = stats["max_armor"]
    player["attack"] = stats["attack"]
    player["armor"] = max(0, min(player["armor"], stats["max_armor"]))
    for special in unlocked_specials(player["points"]):
        if special not in player["specials"] and special not in player["used_specials"]:
            player["specials"].append(special)
    player["equipped"] = player["specials"][-1] if player["specials"] else None


def use_special(name: str, actor: dict, opponent: dict) -> str:
    actor["specials"].remove(name)
    actor["used_specials"].append(name)

    if name == "drain":
        opponent["points"] = max(0, opponent["points"] - config.DRAIN_AMOUNT)
        detail = f"Drained {config.DRAIN_AMOUNT} points from {opponent['username']}"
    elif name == "swap_points":
        actor["points"], opponent["points"] = opponent["points"], actor["points"]
        detail = "Points swapped"
    elif name == "swap_skill":
        actor["specials"], opponent["specials"] = opponent["specials"], actor["specials"]
        detail = "Skills swapped"
    elif name == "clear_skill":
        opponent["used_specials"].extend(opponent["specials"])
        opponent["specials"] = []
        detail = f"Cleared {opponent['username']}'s skills"
    else:
        raise ValueError("unknown special")

    for player in (actor, opponent):
        sync_player(player)
    return detail


def heal(player: dict, now: float | None = None) -> str:
    now = time.monotonic() if now is None else now
    if player["points"] < config.HEAL_COST:
        raise ValueError(f"healing costs {config.HEAL_COST} points")
    remaining = config.HEAL_COOLDOWN - (now - player["last_heal"])
    if remaining > 0:
        raise ValueError(f"healing available in {remaining:.0f}s")
    player["points"] -= config.HEAL_COST
    player["armor"] = min(player["max_armor"], player["armor"] + config.HEAL_AMOUNT)
    player["last_heal"] = now
    sync_player(player)
    return f"Repaired {config.HEAL_AMOUNT} armor"
