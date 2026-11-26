import time

import pytest

from app import config
from app.game.rules import (
    activate_skill,
    apply_damage,
    is_blocked,
    new_player,
    regenerate_armor,
    regenerate_health,
    regenerate_skill,
    score_word,
)

POOL = list(config.SKILLS)


def test_scoring():
    assert score_word("cat") == 3
    assert score_word("spell") == 10


def test_stats_from_points():
    player = new_player(1, "a", POOL)
    player["points"] = 20
    from app.game.rules import sync_player

    sync_player(player, POOL)
    assert player["max_health"] == config.HEALTH_BASE + 20 * config.HEALTH_PER_POINT
    assert player["attack"] == min(
        config.ATTACK_CAP, config.ATTACK_BASE + 20 * config.ATTACK_PER_POINT
    )


def test_regeneration_caps_and_cooldown():
    player = new_player(1, "a", POOL)
    player["health"] = 1
    player["points"] = 100
    assert "Restored" in regenerate_health(player, now=100)
    assert player["health"] == round(player["max_health"] * config.HEALTH_REGEN_PERCENT) + 1
    try:
        regenerate_health(player, now=101)
    except ValueError:
        pass
    else:
        raise AssertionError("cooldown was not enforced")

    player["armor"] = 1
    assert "Restored" in regenerate_armor(player, now=100)


def test_damage_absorbs_armor_first():
    attacker = new_player(1, "a", POOL)
    defender = new_player(2, "b", POOL)
    defender["armor"] = 1
    apply_damage(attacker, defender)
    assert defender["armor"] == 0
    assert defender["health"] == config.HEALTH_BASE - (attacker["attack"] - 1)


def test_skill_effects():
    now = time.monotonic()
    actor = new_player(1, "a", POOL)
    opponent = new_player(2, "b", POOL)
    opponent["points"] = 100
    actor["skill"] = "BLOCK_POINTS"
    activate_skill(actor, opponent, POOL, now=now)
    assert is_blocked(opponent, now + 1)
    assert not is_blocked(opponent, now + 6)

    actor["skill"] = "REDUCE_POINTS_PERCENT"
    activate_skill(actor, opponent, POOL, now=now)
    assert opponent["points"] == 80

    actor["skill"] = "STEAL_POINTS_RANGE"
    activate_skill(actor, opponent, POOL, now=now)
    assert actor["points"] >= config.STEAL_MIN_POINTS

    actor["skill"] = "SWAP_SKILLS"
    opponent["skill"] = "CLEAR_OPPONENT_SKILL"
    assert activate_skill(actor, opponent, POOL, now=now) == "Skills switched"
    assert actor["skill"] == "CLEAR_OPPONENT_SKILL"
    assert opponent["skill"] == "SWAP_SKILLS"

    actor["skill"] = "SWAP_SKILLS"
    opponent["skill"] = None
    with pytest.raises(ValueError, match="no skill"):
        activate_skill(actor, opponent, POOL, now=now)
    assert actor["skill"] == "SWAP_SKILLS"
    assert opponent["skill"] is None

    opponent["skill"] = "BLOCK_POINTS"
    actor["skill"] = "CLEAR_OPPONENT_SKILL"
    assert activate_skill(actor, opponent, POOL, now=now) == "Opponent skill cleared"
    assert actor["skill"] == "CLEAR_OPPONENT_SKILL"
    assert opponent["skill"] is None


def test_skill_regeneration():
    player = new_player(1, "a", POOL)
    player["points"] = 100
    player["skill"] = None
    assert "New skill" in regenerate_skill(player, POOL, now=100)
    assert player["skill"] in POOL
