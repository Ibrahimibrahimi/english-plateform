from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app import config
from app.auth import current_user

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=config.TEMPLATES_DIR)


def page(request: Request, name: str, **extra):
    user = current_user(request)
    return templates.TemplateResponse(
        request=request,
        name=name,
        context={"request": request, "user": user, **extra},
    )


@router.get("/")
def home(request: Request):
    return page(request, "index.html")


@router.get("/play")
def play(request: Request):
    return page(request, "play.html")


@router.get("/play-with-friend")
def play_with_friend(request: Request):
    return page(request, "play-with-friend.html")


@router.get("/play-challenge")
def play_challenge(request: Request):
    return page(request, "play-challenge.html")


@router.get("/play-tournament")
def play_tournament(request: Request):
    return page(request, "play-tournament.html")


@router.get("/challenge/create")
def challenge_create(request: Request):
    return page(request, "challenge/create.html")


@router.get("/challenge/join")
def challenge_join(request: Request):
    return page(request, "challenge/join.html")


@router.get("/challenge/search")
def challenge_search(request: Request):
    return page(request, "challenge/search.html")


@router.get("/tournament/join")
def tournament_join(request: Request):
    return page(request, "tournament/join.html")


@router.get("/tournament/search")
def tournament_search(request: Request):
    return page(request, "tournament/search.html")


@router.get("/tournament/{tournament_id}")
def tournament_detail(request: Request, tournament_id: int):
    return page(request, "tournament/detail.html", tournament_id=tournament_id)


@router.get("/players")
def players(request: Request):
    return page(request, "players.html")


@router.get("/leaderboard")
def leaderboard(request: Request):
    return page(request, "leaderboard.html")


@router.get("/practice")
def practice(request: Request):
    return page(request, "practice.html")


@router.get("/playing/{match_id}")
def playing(request: Request, match_id: int):
    return page(request, "playing.html", match_id=match_id)


@router.get("/profile")
def profile(request: Request):
    return page(request, "profile.html")


@router.get("/admin")
def admin(request: Request):
    user = current_user(request)
    if user is None or user.role != "admin":
        return page(request, "index.html")
    return page(request, "admin/index.html")
