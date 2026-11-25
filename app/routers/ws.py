import json
import logging

from flask import request
from flask_sock import Sock
from simple_websocket import ConnectionClosed

from app import config
from app.auth import COOKIE_NAME, read_token
from app.game.arena import arena
from app.game.presence import online_ids, touch
from app.game.service import ensure_match

logger = logging.getLogger(__name__)
sock = Sock()


def register(app):
    sock.init_app(app)


def _origin_allowed() -> bool:
    origin = request.headers.get("Origin")
    if origin is None:
        return True
    origin = origin.rstrip("/")
    return origin == request.host_url.rstrip("/") or origin in config.ALLOWED_ORIGINS


def _payload(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="strict")
    if not isinstance(raw, str) or len(raw) > config.WS_MAX_MESSAGE_SIZE:
        return None
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return message if isinstance(message, dict) else None


@sock.route("/ws/match/<int:match_id>")
def match_socket(ws, match_id: int):
    if not _origin_allowed():
        ws.close(4403)
        return
    user_id = read_token(request.cookies.get(COOKIE_NAME))
    if user_id is None:
        ws.close(4401)
        return
    match = arena.get(match_id) or ensure_match(match_id)
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
            message = _payload(raw)
            if message is None:
                match.send_to(user_id, {"type": "error", "message": "Invalid message"})
                continue
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
                match.send_to(user_id, {"type": "pong"})
            else:
                match.send_to(user_id, {"type": "error", "message": "Unknown command"})
    except ConnectionClosed:
        pass
    except UnicodeDecodeError:
        match.send_to(user_id, {"type": "error", "message": "Invalid message"})
    except Exception:
        logger.warning("match websocket failed for match %s", match_id, exc_info=True)
    finally:
        match.disconnect(user_id, ws)


@sock.route("/ws/presence")
def presence_socket(ws):
    if not _origin_allowed():
        ws.close(4403)
        return
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
            if not _payload(raw):
                ws.send(json.dumps({"type": "error", "message": "Invalid message"}))
                continue
            touch(user_id)
            ws.send(json.dumps({"type": "state", "payload": {"online": online_ids()}}))
    except ConnectionClosed:
        pass
    except Exception:
        logger.warning("presence websocket failed", exc_info=True)
