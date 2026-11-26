import base64
import io
import time
import uuid

from app import configs
from app.db import SessionLocal
from app.game.arena import LiveMatch, arena
from app.game.rules import new_player
from app.game.service import new_key
from app.game.words import is_valid_word
from app.main import app
from app.models import Challenge, Match, MatchParticipant

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


def test_avatar_upload_and_preset_clear():
    client = app.test_client()
    user = signup(client, "uploader")
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
    )
    uploaded = client.post(
        "/api/me/avatar",
        data={"image": (io.BytesIO(png), "me.png")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 200, uploaded.get_data(as_text=True)
    avatar = uploaded.get_json()["avatar"]
    assert avatar["key"] == "upload"
    assert avatar["image_url"].startswith(f"{configs.UPLOAD_URL_PREFIX}/avatar-{user['id']}-")
    filename = avatar["image_url"].rsplit("/", 1)[-1]
    path = configs.UPLOAD_DIR / filename
    assert path.exists()

    profile = app.test_client().get(f"/api/players/{user['id']}").get_json()
    assert profile["avatar"]["image_url"] == avatar["image_url"]
    image = app.test_client().get(avatar["image_url"])
    assert image.status_code == 200
    assert image.data == png

    invalid = client.post(
        "/api/me/avatar",
        data={"image": (io.BytesIO(b"not an image"), "fake.png")},
        content_type="multipart/form-data",
    )
    assert invalid.status_code == 400
    assert client.get(f"/api/players/{user['id']}").get_json()["avatar"]["image_url"] == avatar["image_url"]

    cleared = client.patch("/api/me", json={"avatar": "fox"})
    assert cleared.get_json()["avatar"]["image_url"] is None
    assert not path.exists()


def test_friend_requests_and_notifications():
    first_client = app.test_client()
    second_client = app.test_client()
    first = signup(first_client, "friendone")
    second = signup(second_client, "friendtwo")

    from app.game.notifications import notification_hub

    socket = FakeSocket()
    notification_hub.add(second["id"], socket)
    created = first_client.post("/api/friends/requests", json={"user_id": second["id"]})
    assert created.status_code == 201, created.get_data(as_text=True)
    request_id = created.get_json()["id"]
    assert created.get_json()["direction"] == "outgoing"
    assert any(configs.NOTIFICATION_FRIEND_REQUEST_RECEIVED in message for message in socket.messages)
    notification_hub.remove(second["id"], socket)

    incoming = second_client.get("/api/friends").get_json()
    assert len(incoming["incoming"]) == 1
    assert incoming["incoming"][0]["user"]["id"] == first["id"]
    assert second_client.get("/api/friends/count").get_json()["count"] == 1
    assert app.test_client().get(f"/api/players/{second['id']}").get_json()["friend_status"] == "none"
    assert second_client.get(f"/api/players/{first['id']}").get_json()["friend_status"] == "incoming"
    assert first_client.get(f"/api/players/{second['id']}").get_json()["friend_status"] == "outgoing"

    assert first_client.get("/friends").status_code == 200

    accepted = second_client.post(f"/api/friends/requests/{request_id}/accept", json={})
    assert accepted.status_code == 200, accepted.get_data(as_text=True)
    assert accepted.get_json()["friend"]["id"] == first["id"]
    assert [item["id"] for item in first_client.get("/api/friends").get_json()["friends"]] == [second["id"]]
    assert [item["id"] for item in second_client.get("/api/friends").get_json()["friends"]] == [first["id"]]
    assert second_client.get("/api/friends/count").get_json()["count"] == 0
    assert first_client.post("/api/friends/requests", json={"user_id": second["id"]}).status_code == 409


def test_friend_request_decline_can_be_replaced():
    sender_client = app.test_client()
    target_client = app.test_client()
    sender = signup(sender_client, "declinsender")
    target = signup(target_client, "declintarget")
    created = sender_client.post("/api/friends/requests", json={"user_id": target["id"]})
    request_id = created.get_json()["id"]
    declined = target_client.post(f"/api/friends/requests/{request_id}/decline", json={})
    assert declined.status_code == 200
    assert target_client.get("/api/friends/count").get_json()["count"] == 0
    replacement = sender_client.post("/api/friends/requests", json={"user_id": target["id"]})
    assert replacement.status_code == 201
    assert replacement.get_json()["id"] == request_id
    assert target_client.get("/api/friends").get_json()["incoming"][0]["user"]["id"] == sender["id"]


def test_rematch_requires_mutual_agreement_and_challenges_only():
    from app.game.notifications import notification_hub

    first_client = app.test_client()
    second_client = app.test_client()
    first = signup(first_client, "rematchone")
    second = signup(second_client, "rematchtwo")

    socket = FakeSocket()
    notification_hub.add(second["id"], socket)
    created = first_client.post(
        "/api/challenges",
        json={"opponent_id": second["id"], "allowed_letters": configs.DEFAULT_LETTERS},
    )
    created_data = created.get_json()
    key = created_data["key"]
    match_id = created_data["match"]["id"]
    joined = second_client.post(f"/api/challenges/{key}/join", json={})
    assert joined.status_code == 200, joined.get_data(as_text=True)
    arena.get(match_id).finish("rounds", winner_id=first["id"])

    assert b"rematch-panel" in first_client.get(f"/playing/{match_id}").data
    rematch_state = first_client.get(f"/api/matches/{match_id}/rematch")
    assert rematch_state.status_code == 200, rematch_state.get_data(as_text=True)
    assert rematch_state.get_json()["offer"] is None
    offered = first_client.post(f"/api/matches/{match_id}/rematch", json={})
    assert offered.status_code == 201, offered.get_data(as_text=True)
    offer_id = offered.get_json()["id"]
    assert offered.get_json()["direction"] == "outgoing"
    assert any(configs.NOTIFICATION_REMATCH_OFFERED in message for message in socket.messages)
    incoming = second_client.get(f"/api/matches/{match_id}/rematch").get_json()["offer"]
    assert incoming["id"] == offer_id
    assert incoming["can_accept"] is True
    assert first_client.get(f"/api/matches/{match_id}/rematch").get_json()["offer"]["can_accept"] is False

    declined = second_client.post(f"/api/matches/{match_id}/rematch/decline", json={})
    assert declined.status_code == 200
    assert declined.get_json()["status"] == configs.REMATCH_STATUS_DECLINED

    reoffered = first_client.post(f"/api/matches/{match_id}/rematch", json={})
    assert reoffered.status_code == 201
    assert reoffered.get_json()["id"] == offer_id

    accepted = second_client.post(f"/api/matches/{match_id}/rematch/accept", json={})
    assert accepted.status_code == 200, accepted.get_data(as_text=True)
    new_match = accepted.get_json()["match"]
    assert new_match["mode"] == "challenge"
    assert new_match["id"] != match_id
    assert second_client.get(f"/api/matches/{new_match['id']}").status_code == 200
    notification_hub.remove(second["id"], socket)

    db = SessionLocal()
    try:
        tournament = Match(key=new_key("T"), mode="tournament", status="finished")
        db.add(tournament)
        db.flush()
        db.add(MatchParticipant(match_id=tournament.id, user_id=first["id"]))
        db.add(MatchParticipant(match_id=tournament.id, user_id=second["id"]))
        db.commit()
        tournament_id = tournament.id
    finally:
        db.close()
    blocked = first_client.post(f"/api/matches/{tournament_id}/rematch", json={})
    assert blocked.status_code == 403


def test_public_config_centralises_rules():
    data = app.test_client().get("/api/config").get_json()
    assert data["skills"][0]["code"] in configs.SKILLS
    assert data["default_letters"] == configs.DEFAULT_LETTERS
    assert data["default_players"] == configs.DEFAULT_TOURNAMENT_MAX_PLAYERS == 20
    assert data["tournament_min_letters"] == configs.TOURNAMENT_MIN_LETTERS


def test_skill_icons_are_exposed():
    data = app.test_client().get("/api/config").get_json()
    assert all(skill["icon"] for skill in data["skills"])
    assert all(code in configs.SKILL_ICONS for code in configs.SKILLS)

    match, _sockets = make_match()
    try:
        state = match.public_state()["players"]["1"]
        assert state["skill_icon"] == configs.SKILL_ICONS[state["skill"]]
    finally:
        match.finish("abandoned")


def test_admin_dedicated_tournament_page():
    client = admin_client()
    page = client.get("/admin/tournaments/new")
    assert page.status_code == 200
    assert b"Create tournament" in page.data
    assert b"Create tournament" in client.get("/").data  # link in the side menu
    assert app.test_client().get("/admin/tournaments/new").status_code == 200


def test_challenge_timing_settings_round_trip():
    client = app.test_client()
    signup(client, "timing")
    created = client.post(
        "/api/challenges",
        json={
            "allowed_letters": configs.DEFAULT_LETTERS,
            "start_delay_seconds": 7,
            "end_mode": configs.CHALLENGE_END_MODE_INFINITE,
        },
    )
    assert created.status_code == 200
    payload = created.get_json()
    assert payload["start_delay_seconds"] == 7
    assert payload["end_mode"] == configs.CHALLENGE_END_MODE_INFINITE
    assert payload["match"]["start_delay_seconds"] == 7
    assert payload["match"]["end_mode"] == configs.CHALLENGE_END_MODE_INFINITE

    details = client.get(f"/api/challenges/{payload['key']}").get_json()
    assert details["start_delay_seconds"] == 7
    assert details["end_mode"] == configs.CHALLENGE_END_MODE_INFINITE

    db = SessionLocal()
    try:
        challenge = db.get(Challenge, payload["id"])
        match = db.get(Match, payload["match"]["id"])
        assert challenge.start_delay_seconds == 7
        assert challenge.end_mode == configs.CHALLENGE_END_MODE_INFINITE
        assert match.start_delay_seconds == 7
        assert match.end_mode == configs.CHALLENGE_END_MODE_INFINITE
    finally:
        db.close()

    assert client.post(
        "/api/challenges",
        json={"allowed_letters": configs.DEFAULT_LETTERS, "start_delay_seconds": 999},
    ).status_code == 400
    assert client.post(
        "/api/challenges",
        json={"allowed_letters": configs.DEFAULT_LETTERS, "end_mode": "forever"},
    ).status_code == 400


def test_delayed_match_waits_before_starting():
    players = {
        1: new_player(1, "one", POOL),
        2: new_player(2, "two", POOL),
    }
    rounds = [{"index": 0, "letters": configs.DEFAULT_LETTERS, "duration_seconds": 60}]
    match = LiveMatch(9001, players, rounds, POOL, start_delay_seconds=0.05)
    sockets = {1: FakeSocket(), 2: FakeSocket()}
    try:
        assert match.connect(1, sockets[1])
        assert match.connect(2, sockets[2])
        assert match.status == "waiting"
        assert match.public_state()["start_in"] >= 1
        deadline = time.monotonic() + 1
        while match.status == "waiting" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert match.status == "active"
    finally:
        match.finish("abandoned")


def test_infinite_match_continues_after_last_round():
    players = {
        1: new_player(1, "one", POOL),
        2: new_player(2, "two", POOL),
    }
    rounds = [
        {"index": index, "letters": configs.DEFAULT_LETTERS, "duration_seconds": 60}
        for index in range(2)
    ]
    match = LiveMatch(9002, players, rounds, POOL, infinite=True)
    sockets = {1: FakeSocket(), 2: FakeSocket()}
    try:
        assert match.connect(1, sockets[1])
        assert match.connect(2, sockets[2])
        assert match.public_state()["total_rounds"] is None
        match.next_round()
        match.next_round()
        assert match.status == "active"
        assert match.round_index == 2
        assert len(match.rounds) == 3
        match.finish("ko", winner_id=1)
        assert match.status == "finished"
    finally:
        match.finish("abandoned")


def test_training_page_renders():
    response = app.test_client().get("/training")
    assert response.status_code == 200
    assert b"Training arena" in response.data
    assert b"/static/js/training.js" in response.data
