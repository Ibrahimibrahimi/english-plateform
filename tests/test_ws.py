import uuid

from fastapi.testclient import TestClient

from app.main import app

suffix = uuid.uuid4().hex[:6]


def wait_for(websocket, event: str, limit: int = 20):
    for _ in range(limit):
        message = websocket.receive_json()
        if message.get("type") == event or message.get("event") == event:
            return message
    raise AssertionError(f"event {event} was not received")


def test_two_players_receive_authoritative_state():
    with TestClient(app):
        one = TestClient(app)
        two = TestClient(app)
        ids = []
        for client, name in ((one, "wsalpha"), (two, "wsbeta")):
            response = client.post(
                "/api/auth/signup",
                json={
                    "username": f"{name}{suffix}",
                    "email": f"{name}{suffix}@example.com",
                    "password": "password123",
                },
            )
            assert response.status_code == 200, response.text
            ids.append(response.json()["id"])

        challenge = one.post("/api/challenges", json={"allowed_letters": "AEIOURSTLND"})
        assert challenge.status_code == 200, challenge.text
        match_id = challenge.json()["match"]["id"]
        joined = two.post(f"/api/challenges/{challenge.json()['key']}/join", json={})
        assert joined.status_code == 200, joined.text

        with one.websocket_connect(f"/ws/match/{match_id}") as first, two.websocket_connect(
            f"/ws/match/{match_id}"
        ) as second:
            wait_for(first, "round_start")
            wait_for(second, "round_start")
            first.send_json({"type": "answer.submit", "word": "rate", "command_id": "one"})
            result = wait_for(first, "word")
            assert result["payload"]["points"] == 6
            mirrored = wait_for(second, "word")
            assert mirrored["payload"]["points"] == 6
            state = wait_for(second, "state")
            assert state["payload"]["players"][str(ids[0])]["points"] == 6
