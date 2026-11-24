import uuid

from fastapi.testclient import TestClient

from app.main import app

suffix = uuid.uuid4().hex[:6]


def signup(client: TestClient, name: str):
    response = client.post(
        "/api/auth/signup",
        json={
            "username": f"{name}{suffix}",
            "email": f"{name}{suffix}@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_accounts_challenges_tournaments_and_stats():
    with TestClient(app) as admin_client:
        player_one = TestClient(app)
        player_two = TestClient(app)
        one = signup(player_one, "alpha")
        two = signup(player_two, "beta")

        assert player_one.get("/api/auth/me").json()["id"] == one["id"]
        assert player_one.post("/api/tournaments", json={"name": "Forbidden"}).status_code in (401, 403)

        login = admin_client.post(
            "/api/auth/login",
            json={"email": "admin@spellbattle.local", "password": "admin123"},
        )
        assert login.status_code == 200, login.text

        letters = admin_client.post(
            "/admin/api/letter-sets",
            json={"name": f"Letters {suffix}", "letters": "AEIOURSTLND"},
        )
        assert letters.status_code == 200, letters.text

        tournament = admin_client.post(
            "/api/tournaments",
            json={
                "name": f"Cup {suffix}",
                "max_players": 8,
                "allowed_letters": "AEIOURSTLND",
                "skills": "BLOCK_POINTS,STEAL_POINTS_RANGE",
            },
        )
        assert tournament.status_code == 200, tournament.text
        tournament_id = tournament.json()["id"]
        key = tournament.json()["key"]

        first_join = player_one.post(
            f"/api/tournaments/{tournament_id}/join", json={"key": key}
        )
        second_join = player_two.post(
            f"/api/tournaments/{tournament_id}/join", json={"key": key}
        )
        assert first_join.status_code == 200, first_join.text
        assert second_join.status_code == 200, second_join.text
        assert second_join.json()["match"] is not None
        details = player_one.get(f"/api/tournaments/{tournament_id}").json()
        assert len(details["matches"]) == 1
        assert details["matches"][0]["id"] == second_join.json()["match"]["id"]

        challenge = player_one.post(
            "/api/challenges", json={"allowed_letters": "AEIOURSTLND"}
        )
        assert challenge.status_code == 200, challenge.text
        challenge_key = challenge.json()["key"]
        joined = player_two.post(f"/api/challenges/{challenge_key}/join", json={})
        assert joined.status_code == 200, joined.text
        assert joined.json()["status"] == "waiting"

        assert player_one.get("/api/players/online").status_code == 200
        assert player_one.get("/api/me/statistics").status_code == 200
        assert player_one.get("/api/me/history").status_code == 200
        leaderboard = player_one.get("/api/leaderboard").json()
        assert any(entry["username"] == one["username"] for entry in leaderboard)
        assert any(entry["username"] == two["username"] for entry in leaderboard)
