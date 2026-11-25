import uuid

from app import configs
from app.game.arena import LiveMatch
from app.game.rules import new_player
from app.game.words import is_valid_word
from app.main import app

suffix = uuid.uuid4().hex[:6]
POOL = list(configs.SKILLS)


def signup(client, name: str):
    response = client.post(
        "/api/auth/signup",
        json={
            "username": f"{name}{suffix}",
            "email": f"{name}{suffix}@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def admin_client():
    client = app.test_client()
    response = client.post(
        "/api/auth/login",
        json={"email": configs.ADMIN_EMAIL, "password": configs.ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return client


class FakeSocket:
    def __init__(self):
        self.messages = []

    def send(self, text):
        self.messages.append(text)

    def close(self, _code=None):
        pass


def make_match():
    players = {
        1: new_player(1, "one", POOL),
        2: new_player(2, "two", POOL),
    }
    rounds = [
        {"index": index, "letters": configs.DEFAULT_LETTERS, "duration_seconds": 60}
        for index in range(2)
    ]
    match = LiveMatch(1, players, rounds, POOL)
    sockets = {1: FakeSocket(), 2: FakeSocket()}
    for user_id, socket in sockets.items():
        assert match.connect(user_id, socket)
    return match, sockets


def test_default_tournament_has_twenty_players():
    tournaments = app.test_client().get("/api/tournaments").get_json()
    default = [item for item in tournaments if item["name"] == configs.DEFAULT_TOURNAMENT_NAME]
    assert len(default) == 1
    assert default[0]["max_players"] == configs.DEFAULT_TOURNAMENT_MAX_PLAYERS == 20
    assert default[0]["status"] == configs.DEFAULT_TOURNAMENT_STATUS


def test_word_repeats_allowed_and_unique_per_round():
    words = None
    assert is_valid_word("tree", configs.DEFAULT_LETTERS, words)
    assert not is_valid_word("zzyzx", configs.DEFAULT_LETTERS, words)

    match, sockets = make_match()
    try:
        armor = match.players[2]["armor"]
        match.submit_word(1, "tree")
        assert match.players[1]["points"] == 6
        assert match.players[2]["armor"] < armor

        match.submit_word(2, "tree")
        assert match.players[2]["points"] == 0
        assert any("already used" in message for message in sockets[2].messages)

        # The same word stays unavailable to both players in later rounds.
        match.next_round()
        match.submit_word(2, "tree")
        assert match.players[2]["points"] == 0
    finally:
        match.finish("abandoned")


def test_invalid_word_does_not_change_health():
    match, sockets = make_match()
    try:
        before = {
            uid: (state["health"], state["armor"], state["points"])
            for uid, state in match.players.items()
        }
        match.submit_word(1, "zzzzz")
        match.submit_word(1, "notenglish")
        assert {
            uid: (state["health"], state["armor"], state["points"])
            for uid, state in match.players.items()
        } == before
        assert any("Invalid word" in message for message in sockets[1].messages)
    finally:
        match.finish("abandoned")


def test_challenge_list_and_notifications():
    challenger_client = app.test_client()
    invited_client = app.test_client()
    outsider_client = app.test_client()
    challenger = signup(challenger_client, "inviter")
    invited = signup(invited_client, "invitee")
    signup(outsider_client, "watcher")

    from app.game.notifications import notification_hub

    live_socket = FakeSocket()
    notification_hub.add(invited["id"], live_socket)
    created = challenger_client.post(
        "/api/challenges",
        json={"opponent_id": invited["id"], "allowed_letters": configs.DEFAULT_LETTERS},
    )
    assert created.status_code == 200, created.get_data(as_text=True)
    key = created.get_json()["key"]

    assert any("notification" in message for message in live_socket.messages)
    notification_hub.remove(invited["id"], live_socket)

    notifications = invited_client.get("/api/notifications").get_json()
    assert notifications["unread_count"] >= 1
    assert any(
        item["type"] == configs.NOTIFICATION_CHALLENGE_RECEIVED and key in item["link"]
        for item in notifications["items"]
    )

    invited_listing = invited_client.get("/api/challenges").get_json()
    assert any(item["key"] == key and item["for_you"] for item in invited_listing)

    open_challenge = challenger_client.post(
        "/api/challenges", json={"allowed_letters": configs.DEFAULT_LETTERS}
    )
    assert open_challenge.status_code == 200
    open_key = open_challenge.get_json()["key"]
    listing = outsider_client.get("/api/challenges").get_json()
    assert any(item["key"] == open_key and item["creator"]["id"] == challenger["id"] for item in listing)
    assert all(item["key"] != key for item in listing)  # targeted challenge stays private
    creator_listing = challenger_client.get("/api/challenges").get_json()
    assert all(item["key"] not in (key, open_key) for item in creator_listing)

    joined = invited_client.post(f"/api/challenges/{key}/join", json={})
    assert joined.status_code == 200, joined.get_data(as_text=True)
    creator_notifications = challenger_client.get("/api/notifications").get_json()
    assert any(item["type"] == configs.NOTIFICATION_CHALLENGE_JOINED for item in creator_notifications["items"])

    read = invited_client.post("/api/notifications/read", json={})
    assert read.status_code == 200
    assert invited_client.get("/api/notifications").get_json()["unread_count"] == 0


def test_tournament_search_is_injection_safe():
    client = admin_client()
    malicious_name = "Cup' OR 1=1 --"
    created = client.post(
        "/admin/api/tournaments",
        json={"name": malicious_name, "max_players": 4, "allowed_letters": configs.DEFAULT_LETTERS},
    )
    assert created.status_code == 200, created.get_data(as_text=True)
    assert created.get_json()["name"] == malicious_name

    for term in ["%' OR 1=1 --", "' DROP TABLE tournaments; --", "100%_"]:
        response = app.test_client().get("/api/tournaments", query_string={"search": term})
        assert response.status_code == 200
        assert all(item["name"] != malicious_name or term in malicious_name for item in response.get_json())

    actions = client.get("/admin/api/actions").get_json()
    assert any(action["action"] == "tournament.created" for action in actions)


def test_avatar_choice_and_public_profile():
    client = app.test_client()
    user = signup(client, "avatar")
    updated = client.patch("/api/me", json={"avatar": "fox"})
    assert updated.status_code == 200
    assert updated.get_json()["avatar"]["key"] == "fox"

    profile = app.test_client().get(f"/api/players/{user['id']}")
    assert profile.status_code == 200
    assert profile.get_json()["avatar"]["key"] == "fox"
    assert "email" not in profile.get_json()

    fallback = client.patch("/api/me", json={"avatar": "<script>alert(1)</script>"})
    assert fallback.get_json()["avatar"]["key"] == configs.DEFAULT_AVATAR

    board = app.test_client().get("/api/leaderboard").get_json()
    assert board[0]["rank"] == 1
    assert all("avatar" in entry and "profile_url" in entry for entry in board)


def test_public_config_centralises_rules():
    data = app.test_client().get("/api/config").get_json()
    assert data["skills"][0]["code"] in configs.SKILLS
    assert data["default_letters"] == configs.DEFAULT_LETTERS
    assert data["default_players"] == configs.DEFAULT_TOURNAMENT_MAX_PLAYERS == 20
    assert data["tournament_min_letters"] == configs.TOURNAMENT_MIN_LETTERS


def test_admin_dedicated_tournament_page():
    client = admin_client()
    page = client.get("/admin/tournaments/new")
    assert page.status_code == 200
    assert b"Create tournament" in page.data
    assert b"Create tournament" in client.get("/").data  # link in the side menu
    assert app.test_client().get("/admin/tournaments/new").status_code == 200
