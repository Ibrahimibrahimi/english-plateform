import uuid

from app.main import app

suffix = uuid.uuid4().hex[:6]


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


def test_accounts_challenges_tournaments_and_stats():
    admin_client = app.test_client()
    player_one = app.test_client()
    player_two = app.test_client()
    one = signup(player_one, "alpha")
    two = signup(player_two, "beta")

    assert player_one.get("/api/auth/me").get_json()["id"] == one["id"]
    assert player_one.post("/api/tournaments", json={"name": "Forbidden"}).status_code in (401, 403)

    login = admin_client.post(
        "/api/auth/login",
        json={"email": "admin@spellbattle.local", "password": "admin123"},
    )
    assert login.status_code == 200, login.get_data(as_text=True)

    letters = admin_client.post(
        "/admin/api/letter-sets",
        json={"name": f"Letters {suffix}", "letters": "AEIOURSTLND"},
    )
    assert letters.status_code == 200, letters.get_data(as_text=True)

    tournament = admin_client.post(
        "/api/tournaments",
        json={
            "name": f"Cup {suffix}",
            "max_players": 8,
            "allowed_letters": "AEIOURSTLND",
            "skills": "BLOCK_POINTS,STEAL_POINTS_RANGE",
        },
    )
    assert tournament.status_code == 200, tournament.get_data(as_text=True)
    tournament_id = tournament.get_json()["id"]
    key = tournament.get_json()["key"]

    first_join = player_one.post(
        f"/api/tournaments/{tournament_id}/join", json={"key": key}
    )
    second_join = player_two.post(
        f"/api/tournaments/{tournament_id}/join", json={"key": key}
    )
    assert first_join.status_code == 200, first_join.get_data(as_text=True)
    assert second_join.status_code == 200, second_join.get_data(as_text=True)
    assert second_join.get_json()["match"] is not None
    details = player_one.get(f"/api/tournaments/{tournament_id}").get_json()
    assert len(details["matches"]) == 1
    assert details["matches"][0]["id"] == second_join.get_json()["match"]["id"]

    challenge = player_one.post(
        "/api/challenges", json={"allowed_letters": "AEIOURSTLND"}
    )
    assert challenge.status_code == 200, challenge.get_data(as_text=True)
    challenge_key = challenge.get_json()["key"]
    joined = player_two.post(f"/api/challenges/{challenge_key}/join", json={})
    assert joined.status_code == 200, joined.get_data(as_text=True)
    assert joined.get_json()["status"] == "waiting"

    assert player_one.get("/api/players/online").status_code == 200
    assert player_one.get("/api/me/statistics").status_code == 200
    assert player_one.get("/api/me/history").status_code == 200
    leaderboard = player_one.get("/api/leaderboard").get_json()
    assert any(entry["username"] == one["username"] for entry in leaderboard)
    assert any(entry["username"] == two["username"] for entry in leaderboard)


def test_profile_update_persists_and_validates_names():
    client = app.test_client()
    signup(client, "profile")
    updated = client.patch("/api/me", json={"username": f"renamed{suffix}"})
    assert updated.status_code == 200, updated.get_data(as_text=True)
    assert updated.get_json()["username"] == f"renamed{suffix}"
    assert client.get("/api/auth/me").get_json()["username"] == f"renamed{suffix}"

    invalid = client.patch("/api/me", json={"username": "not allowed!"})
    assert invalid.status_code == 400
    duplicate = app.test_client()
    signup(duplicate, "dupe")
    conflict = duplicate.patch("/api/me", json={"username": f"renamed{suffix}"})
    assert conflict.status_code == 409


def test_privacy_and_match_snapshot_authorization():
    owner_client = app.test_client()
    opponent_client = app.test_client()
    outsider_client = app.test_client()
    signup(owner_client, "privacyone")
    opponent = signup(opponent_client, "privacytwo")
    signup(outsider_client, "privacythree")

    challenge = owner_client.post("/api/challenges", json={"allowed_letters": "AEIOURSTLND"})
    assert challenge.status_code == 200, challenge.get_data(as_text=True)
    challenge_payload = challenge.get_json()
    match_id = challenge_payload["match"]["id"]
    joined = opponent_client.post(f"/api/challenges/{challenge_payload['key']}/join", json={})
    assert joined.status_code == 200, joined.get_data(as_text=True)

    online = owner_client.get("/api/players/online")
    assert online.status_code == 200
    entries = online.get_json()
    assert any(entry["id"] == opponent["id"] for entry in entries)
    assert all("email" not in entry for entry in entries)

    assert app.test_client().get(f"/api/matches/{match_id}").status_code == 401
    outsider_snapshot = outsider_client.get(f"/api/matches/{match_id}")
    assert outsider_snapshot.status_code == 403
    owner_snapshot = owner_client.get(f"/api/matches/{match_id}")
    assert owner_snapshot.status_code == 200, owner_snapshot.get_data(as_text=True)
    assert owner_snapshot.get_json()["state"]["status"] == "waiting"

    forbidden_key = app.test_client().get(f"/api/challenges/{challenge_payload['key']}")
    assert forbidden_key.status_code == 401


def test_tournament_keys_are_private_and_join_by_key_works():
    admin_client = app.test_client()
    login = admin_client.post(
        "/api/auth/login",
        json={"email": "admin@spellbattle.local", "password": "admin123"},
    )
    assert login.status_code == 200, login.get_data(as_text=True)
    tournament = admin_client.post(
        "/api/tournaments",
        json={"name": f"Private Cup {suffix}", "max_players": 8, "allowed_letters": "AEIOURSTLND"},
    )
    assert tournament.status_code == 200, tournament.get_data(as_text=True)
    payload = tournament.get_json()

    public_list = app.test_client().get("/api/tournaments").get_json()
    assert all("key" not in item for item in public_list)
    details = app.test_client().get(f"/api/tournaments/{payload['id']}").get_json()
    assert "key" not in details
    assert details["requires_key"] is True

    first_client = app.test_client()
    second_client = app.test_client()
    signup(first_client, "keyjoinone")
    signup(second_client, "keyjointwo")
    first = first_client.post("/api/tournaments/join", json={"key": payload["key"]})
    assert first.status_code == 200, first.get_data(as_text=True)
    assert first.get_json()["match"]["status"] == "waiting"
    second = second_client.post("/api/tournaments/join", json={"key": payload["key"]})
    assert second.status_code == 200, second.get_data(as_text=True)
    assert second.get_json()["match"]["id"] == first.get_json()["match"]["id"]


def test_open_tournament_join_without_key_and_idempotent_resume():
    admin_client = app.test_client()
    login = admin_client.post(
        "/api/auth/login",
        json={"email": "admin@spellbattle.local", "password": "admin123"},
    )
    assert login.status_code == 200, login.get_data(as_text=True)
    tournament = admin_client.post(
        "/api/tournaments",
        json={
            "name": f"Open Cup {suffix}",
            "max_players": 8,
            "allowed_letters": "AEIOURSTLND",
            "requires_key": False,
        },
    )
    assert tournament.status_code == 200, tournament.get_data(as_text=True)
    tid = tournament.get_json()["id"]

    one = app.test_client()
    two = app.test_client()
    user_one = signup(one, "openone")
    signup(two, "opentwo")

    first = one.post(f"/api/tournaments/{tid}/join", json={})
    assert first.status_code == 200, first.get_data(as_text=True)
    match_id = first.get_json()["match"]["id"]
    assert first.get_json()["match"]["status"] == "waiting"

    repeat = one.post(f"/api/tournaments/{tid}/join", json={})
    assert repeat.status_code == 200, repeat.get_data(as_text=True)
    assert repeat.get_json()["match"]["id"] == match_id

    details = one.get(f"/api/tournaments/{tid}").get_json()
    assert details["requires_key"] is False
    assert details["viewer_participant"]["id"] == user_one["id"]
    assert details["viewer_match"]["id"] == match_id

    second = two.post(f"/api/tournaments/{tid}/join", json={})
    assert second.status_code == 200, second.get_data(as_text=True)
    assert second.get_json()["match"]["id"] == match_id
