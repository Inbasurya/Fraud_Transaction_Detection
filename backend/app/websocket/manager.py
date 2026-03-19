"""WebSocket connection manager — broadcasts to rooms (stream / alerts)."""

from typing import Dict, Set
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        self._rooms.setdefault(room, set()).add(websocket)
        logger.info("WS client connected to room=%s  (total=%d)", room, len(self._rooms[room]))

    def disconnect(self, room: str, websocket: WebSocket):
        self._rooms.get(room, set()).discard(websocket)

    async def broadcast(self, room: str, payload: dict):
        dead: list[WebSocket] = []
        text = json.dumps(payload, default=str)
        for ws in list(self._rooms.get(room, [])):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room, ws)

    @property
    def stream_count(self) -> int:
        return len(self._rooms.get("stream", set()))

    @property
    def alert_count(self) -> int:
        return len(self._rooms.get("alerts", set()))


ws_manager = ConnectionManager()
