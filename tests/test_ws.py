import json
import uuid

from app.main import app

suffix = uuid.uuid4().hex[:6]


class FakeWS:
    def __init__(self):
        self.messages = []
        self.closed = False

    def send(self, data):
        self.messages.append(json.loads(data))

    def close(self, code=None):
        self.closed = True

    def wait_for(self, event: str, limit: int = 40):
        for message in self.messages:
            if message.get("type") == event or message.get("event") == event:
                return message
        raise AssertionError(f"event {event} was not received in {self.messages}")

    def wait_for_state(self, player_id: int, points: int):
        for message in reversed(self.messages):
            if message.get("type") == "state":
                players = message.get("payload", {}).get("players", {})
                if players.get(str(player_id), {}).get("points") == points:
                    return message
        raise AssertionError(f"state with {player_id}={points} not found: {self.messages}")


def signup(client, name):
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


def test_two_players_receive_authoritative_state():
    one = app.test_client()
    two = app.test_client()
    ids = []
    for client, name in ((one, "wsalpha"), (two, "wsbeta")):
        ids.append(signup(client, name)["id"])

    challenge = one.post("/api/challenges", json={"allowed_letters": "AEIOURSTLND"})
    assert challenge.status_code == 200, challenge.get_data(as_text=True)
    payload = challenge.get_json()
    match_id = payload["match"]["id"]
    joined = two.post(f"/api/challenges/{payload['key']}/join", json={})
    assert joined.status_code == 200, joined.get_data(as_text=True)

    from app.game.arena import arena

    live = arena.get(match_id)
    assert live is not None
    ws1, ws2 = FakeWS(), FakeWS()
    assert live.connect(ids[0], ws1)
    assert live.connect(ids[1], ws2)
    ws1.wait_for("round_start")
    ws2.wait_for("round_start")
    live.submit_word(ids[0], "rate", "one")
    result = ws1.wait_for("word")
    assert result["payload"]["points"] == 6
    mirrored = ws2.wait_for("word")
    assert mirrored["payload"]["points"] == 6
    state = ws2.wait_for_state(ids[0], 6)
    assert state["payload"]["players"][str(ids[0])]["points"] == 6
