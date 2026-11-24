from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth import COOKIE_NAME, read_token
from app.game.arena import arena
from app.game.presence import online_ids, touch

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/match/{match_id}")
async def match_socket(websocket: WebSocket, match_id: int):
    user_id = read_token(websocket.cookies.get(COOKIE_NAME))
    if user_id is None:
        await websocket.close(code=4401)
        return
    match = arena.get(match_id)
    if match is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    touch(user_id)
    if not await match.connect(user_id, websocket):
        await websocket.close(code=4403)
        return
    try:
        while True:
            message = await websocket.receive_json()
            command = message.get("type", "")
            if command in ("answer.submit", "submit_word"):
                await match.submit_word(user_id, message.get("word", ""), message.get("command_id", ""))
            elif command in ("skill.regenerate", "regenerate_skill"):
                await match.regenerate(user_id, "skill")
            elif command in ("skill.activate", "special"):
                await match.activate_skill(user_id)
            elif command in ("resource.regenerate", "regenerate"):
                await match.regenerate(user_id, message.get("resource", "health"))
            elif command == "match.leave":
                break
            elif command == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        match.disconnect(user_id)


@router.websocket("/ws/presence")
async def presence_socket(websocket: WebSocket):
    user_id = read_token(websocket.cookies.get(COOKIE_NAME))
    if user_id is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    touch(user_id)
    try:
        while True:
            await websocket.receive_json()
            touch(user_id)
            await websocket.send_json({"type": "state", "payload": {"online": online_ids()}})
    except WebSocketDisconnect:
        pass
