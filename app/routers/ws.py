import json

from flask import request
from flask_sock import Sock
from simple_websocket import ConnectionClosed

from app.auth import COOKIE_NAME, read_token
from app.game.arena import arena
from app.game.presence import online_ids, touch

sock = Sock()


def register(app):
    sock.init_app(app)


@sock.route("/ws/match/<int:match_id>")
def match_socket(ws, match_id: int):
    user_id = read_token(request.cookies.get(COOKIE_NAME))
    if user_id is None:
        ws.close(4401)
        return
    match = arena.get(match_id)
    if match is None:
        ws.close(4404)
        return
    touch(user_id)
    if not match.connect(user_id, ws):
        ws.close(4403)
        return
    try:
        while True:
            raw = ws.receive()
            if raw is None:
                break
            message = json.loads(raw) if isinstance(raw, str) else raw
            command = message.get("type", "")
            if command in ("answer.submit", "submit_word"):
                match.submit_word(user_id, message.get("word", ""), message.get("command_id", ""))
            elif command in ("skill.regenerate", "regenerate_skill"):
                match.regenerate(user_id, "skill")
            elif command in ("skill.activate", "special"):
                match.activate_skill(user_id)
            elif command in ("resource.regenerate", "regenerate"):
                match.regenerate(user_id, message.get("resource", "health"))
            elif command == "match.leave":
                break
            elif command == "ping":
                ws.send(json.dumps({"type": "pong"}))
    except (ConnectionClosed, Exception):
        return
    finally:
        match.disconnect(user_id)


@sock.route("/ws/presence")
def presence_socket(ws):
    user_id = read_token(request.cookies.get(COOKIE_NAME))
    if user_id is None:
        ws.close(4401)
        return
    touch(user_id)
    try:
        while True:
            raw = ws.receive()
            if raw is None:
                break
            touch(user_id)
            ws.send(json.dumps({"type": "state", "payload": {"online": online_ids()}}))
    except (ConnectionClosed, Exception):
        return
