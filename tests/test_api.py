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
