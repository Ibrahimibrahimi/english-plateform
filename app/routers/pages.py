from flask import Blueprint, render_template

from app import configs
from app.auth import avatar_info, current_user

router = Blueprint("pages", __name__)


def page(name: str, **extra):
    user = current_user()
    return render_template(name, user=user, avatar=avatar_info(user) if user else None, **extra)


@router.get("/")
def home():
    return page("index.html")


@router.get("/play")
def play():
    return page("play.html")


@router.get("/play-with-friend")
def play_with_friend():
    return page("play-with-friend.html")


@router.get("/play-challenge")
def play_challenge():
    return page("play-challenge.html")


@router.get("/play-tournament")
def play_tournament():
    return page("play-tournament.html")


@router.get("/challenge/create")
def challenge_create():
    return page(
        "challenge/create.html",
        default_letters=configs.DEFAULT_LETTERS,
        min_letters=configs.CHALLENGE_MIN_LETTERS,
        max_letters=configs.CHALLENGE_MAX_LETTERS,
        delay_min=configs.CHALLENGE_DELAY_MIN_SECONDS,
        delay_max=configs.CHALLENGE_DELAY_MAX_SECONDS,
        end_modes=configs.CHALLENGE_END_MODES,
        rounds_per_match=configs.ROUNDS_PER_MATCH,
    )


@router.get("/challenge/join")
def challenge_join():
    return page("challenge/join.html")


@router.get("/challenge/search")
def challenge_search():
    return page("challenge/search.html")


@router.get("/challenge/list")
def challenge_list():
    return page("challenge/list.html")


@router.get("/tournament/join")
def tournament_join():
    return page("tournament/join.html")


@router.get("/tournament/search")
def tournament_search():
    return page("tournament/search.html")


@router.get("/tournament/<int:tournament_id>")
def tournament_detail(tournament_id: int):
    return page("tournament/detail.html", tournament_id=tournament_id)


@router.get("/players")
def players():
    return page("players.html")


@router.get("/friends")
def friends():
    return page("friends.html")


@router.get("/player/<int:user_id>")
def player_profile(user_id: int):
    return page("player-profile.html", profile_id=user_id)


@router.get("/leaderboard")
def leaderboard():
    return page("leaderboard.html")


@router.get("/practice")
def practice():
    return page("practice.html")


@router.get("/training")
def training():
    return page(
        "training.html",
        default_letters=configs.DEFAULT_LETTERS,
        dummy_health=configs.HEALTH_CAP,
        attack_base=configs.ATTACK_BASE,
        attack_per_point=configs.ATTACK_PER_POINT,
        attack_cap=configs.ATTACK_CAP,
    )


@router.get("/playing/<int:match_id>")
def playing(match_id: int):
    return page("playing.html", match_id=match_id)


@router.get("/profile")
def profile():
    return page(
        "profile.html",
        avatars=configs.AVATARS,
        current_avatar=getattr(current_user(), "avatar", configs.DEFAULT_AVATAR),
        avatar_max_bytes=configs.AVATAR_UPLOAD_MAX_BYTES,
    )


def _admin_config():
    return {
        "min_letters": configs.MIN_LETTERS,
        "max_letters": configs.MAX_LETTERS,
        "min_players": configs.MIN_TOURNAMENT_PLAYERS,
        "max_players": configs.MAX_TOURNAMENT_PLAYERS,
        "default_players": configs.DEFAULT_TOURNAMENT_MAX_PLAYERS,
        "default_letters": configs.DEFAULT_LETTERS,
    }


@router.get("/admin")
def admin():
    user = current_user()
    if user is None or user.role != "admin":
        return page("index.html")
    return page("admin/index.html", **_admin_config())


@router.get("/admin/tournaments/new")
def admin_create_tournament():
    """Dedicated admin page for creating tournaments."""
    user = current_user()
    if user is None or user.role != "admin":
        return page("index.html")
    return page("admin/tournament-create.html", **_admin_config())
