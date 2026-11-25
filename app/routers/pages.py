from flask import Blueprint, render_template

from app.auth import current_user

router = Blueprint("pages", __name__)


def page(name: str, **extra):
    return render_template(name, user=current_user(), **extra)


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
    return page("challenge/create.html")


@router.get("/challenge/join")
def challenge_join():
    return page("challenge/join.html")


@router.get("/challenge/search")
def challenge_search():
    return page("challenge/search.html")


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


@router.get("/leaderboard")
def leaderboard():
    return page("leaderboard.html")


@router.get("/practice")
def practice():
    return page("practice.html")


@router.get("/playing/<int:match_id>")
def playing(match_id: int):
    return page("playing.html", match_id=match_id)


@router.get("/profile")
def profile():
    return page("profile.html")


@router.get("/admin")
def admin():
    user = current_user()
    if user is None or user.role != "admin":
        return page("index.html")
    return page("admin/index.html")
