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


def _challenge_pair(prefix: str):
    one = app.test_client()
    two = app.test_client()
    one_data = signup(one, f"{prefix}one")
    two_data = signup(two, f"{prefix}two")
    challenge = one.post("/api/challenges", json={"allowed_letters": "AEIOURSTLND"})
    assert challenge.status_code == 200, challenge.get_data(as_text=True)
    payload = challenge.get_json()
    joined = two.post(f"/api/challenges/{payload['key']}/join", json={})
    assert joined.status_code == 200, joined.get_data(as_text=True)
    return one, two, one_data, two_data, payload["match"]["id"]


def test_challenge_waits_for_both_players_to_connect():
    from app.game.arena import arena

    _, _, one, two, match_id = _challenge_pair("waiting")
    live = arena.get(match_id)
    assert live is not None
    assert live.status == "waiting"

    first_ws = FakeWS()
    assert live.connect(one["id"], first_ws)
    assert live.status == "waiting"
    first_ws.wait_for("state")

    second_ws = FakeWS()
    assert live.connect(two["id"], second_ws)
    assert live.status == "active"
    first_ws.wait_for("round_start")
    second_ws.wait_for("round_start")


def test_tournament_match_waits_for_both_connections():
    from app.game.arena import arena

    admin_client = app.test_client()
    login = admin_client.post(
        "/api/auth/login",
        json={"email": "admin@spellbattle.local", "password": "admin123"},
    )
    assert login.status_code == 200, login.get_data(as_text=True)
    tournament = admin_client.post(
        "/api/tournaments",
        json={"name": f"Socket Cup {suffix}", "max_players": 4, "allowed_letters": "AEIOURSTLND"},
    )
    assert tournament.status_code == 200, tournament.get_data(as_text=True)
    tournament_payload = tournament.get_json()

    one = app.test_client()
    two = app.test_client()
    one_data = signup(one, "tourneywsone")
    two_data = signup(two, "tourneywstwo")
    first = one.post(f"/api/tournaments/{tournament_payload['id']}/join", json={"key": tournament_payload["key"]})
    assert first.status_code == 200, first.get_data(as_text=True)
    match_id = first.get_json()["match"]["id"]
    second = two.post(f"/api/tournaments/{tournament_payload['id']}/join", json={"key": tournament_payload["key"]})
    assert second.status_code == 200, second.get_data(as_text=True)
    assert second.get_json()["match"]["id"] == match_id

    live = arena.get(match_id)
    assert live is not None and live.status == "waiting"
    first_ws = FakeWS()
    assert live.connect(one_data["id"], first_ws)
    assert live.status == "waiting"
    second_ws = FakeWS()
    assert live.connect(two_data["id"], second_ws)
    assert live.status == "active"
    first_ws.wait_for("round_start")
    second_ws.wait_for("round_start")


def test_reconnecting_replaces_old_socket_without_losing_new_one():
    from app.game.arena import arena

    _, _, one, two, match_id = _challenge_pair("reconnect")
    live = arena.get(match_id)
    old_ws = FakeWS()
    new_ws = FakeWS()
    assert live.connect(one["id"], old_ws)
    assert live.connect(one["id"], new_ws)
    assert old_ws.closed
    live.disconnect(one["id"], old_ws)
    assert live.players[one["id"]]["connected"] is True
    assert live.connections[one["id"]] is new_ws

    second_ws = FakeWS()
    assert live.connect(two["id"], second_ws)
    assert live.status == "active"
    new_ws.wait_for("round_start")
    second_ws.wait_for("round_start")


def test_match_start_and_result_are_persisted():
    from app.db import SessionLocal
    from app.game.arena import arena
    from app.models import Match, MatchParticipant, User

    _, _, one, two, match_id = _challenge_pair("persist")
    live = arena.get(match_id)
    first_ws = FakeWS()
    second_ws = FakeWS()
    assert live.connect(one["id"], first_ws)
    assert live.connect(two["id"], second_ws)

    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        assert match.status == "active"
        assert match.started_at is not None
        assert match.round_index == 0
    finally:
        db.close()

    live.finish("test_complete", winner_id=one["id"])

    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        assert match.status == "finished"
        assert match.winner_id == one["id"]
        assert match.end_reason == "test_complete"
        participants = db.query(MatchParticipant).filter_by(match_id=match_id).all()
        assert len(participants) == 2
        assert all(participant.status == "finished" for participant in participants)
        winner = db.get(User, one["id"])
        loser = db.get(User, two["id"])
        assert winner.wins == 1
        assert loser.losses == 1
    finally:
        db.close()


def test_ensure_match_rebuilds_waiting_match_after_registry_loss():
    from app.game.arena import arena
    from app.game.service import ensure_match

    _, _, one, _, match_id = _challenge_pair("ensure")
    arena.remove(match_id)
    assert arena.get(match_id) is None
    live = ensure_match(match_id)
    assert live is not None
    assert live.status == "waiting"
    assert one["id"] in live.players
    arena.remove(match_id)


def _receive_until(ws, message_type: str, timeout: float = 5.0):
    import time

    deadline = time.monotonic() + timeout
    seen = []
    while time.monotonic() < deadline:
        raw = ws.receive(timeout=max(0.01, deadline - time.monotonic()))
        if raw is None:
            continue
        message = json.loads(raw)
        seen.append(message)
        if message.get("type") == message_type or message.get("event") == message_type:
            return message, seen
    raise AssertionError(f"{message_type} not received: {seen}")


def test_real_websocket_round_trip_uses_session_cookie():
    import threading

    from simple_websocket import Client
    from werkzeug.serving import make_server

    one = app.test_client()
    two = app.test_client()
    ids = [signup(one, "liveone")["id"], signup(two, "livetwo")["id"]]
    cookies = [one.get_cookie("sb_session").value, two.get_cookie("sb_session").value]
    challenge = one.post("/api/challenges", json={"allowed_letters": "AEIOURSTLND"})
    assert challenge.status_code == 200, challenge.get_data(as_text=True)
    payload = challenge.get_json()
    match_id = payload["match"]["id"]
    joined = two.post(f"/api/challenges/{payload['key']}/join", json={})
    assert joined.status_code == 200, joined.get_data(as_text=True)

    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    first = second = None
    try:
        url = f"ws://127.0.0.1:{server.server_port}/ws/match/{match_id}"
        first = Client.connect(url, headers={"Cookie": f"sb_session={cookies[0]}"})
        second = Client.connect(url, headers={"Cookie": f"sb_session={cookies[1]}"})
        state, _ = _receive_until(first, "state")
        assert state["payload"]["status"] == "waiting"
        _receive_until(first, "round_start")
        _receive_until(second, "round_start")

        first.send(json.dumps({"type": "answer.submit", "word": "rate"}))
        word, _ = _receive_until(second, "word")
        assert word["payload"]["user_id"] == ids[0]
        assert word["payload"]["points"] == 6
    finally:
        if first is not None:
            first.close()
        if second is not None:
            second.close()
        server.shutdown()
        thread.join(timeout=5)
