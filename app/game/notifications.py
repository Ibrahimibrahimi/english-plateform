"""Small in-process hub that pushes realtime notifications to players.

Notifications are also persisted in the database (see ``app.models.Notification``),
so the hub is only a delivery mechanism; a missed push is recovered by the
browser when it loads ``/api/notifications``.
"""

import json
import logging
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)


class NotificationHub:
    def __init__(self):
        self._connections: dict[int, set] = defaultdict(set)
        self._lock = threading.RLock()

    def add(self, user_id: int, websocket) -> None:
        with self._lock:
            self._connections[user_id].add(websocket)

    def remove(self, user_id: int, websocket) -> None:
        with self._lock:
            sockets = self._connections.get(user_id)
            if sockets is None:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user_id, None)

    def send(self, user_id: int, message: dict) -> bool:
        """Push a message to every open notification socket of a player."""
        delivered = False
        with self._lock:
            sockets = tuple(self._connections.get(user_id, ()))
        payload = json.dumps(message)
        for websocket in sockets:
            try:
                websocket.send(payload)
                delivered = True
            except Exception:
                logger.debug("notification socket send failed for user %s", user_id, exc_info=True)
        return delivered


notification_hub = NotificationHub()
