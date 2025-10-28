from typing import Dict, Set
from fastapi import WebSocket
import asyncio


class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> set of websockets
        self.active: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: int, websocket: WebSocket):
        async with self._lock:
            conns = self.active.get(user_id)
            if conns and websocket in conns:
                conns.remove(websocket)
            if conns and len(conns) == 0:
                self.active.pop(user_id, None)

    async def send_personal(self, user_id: int, message: dict):
        async with self._lock:
            conns = list(self.active.get(user_id, []))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                # best effort cleanup
                await self.disconnect(user_id, ws)

    async def broadcast_multi(self, user_ids: Set[int], message: dict):
        for uid in user_ids:
            await self.send_personal(uid, message)


manager = ConnectionManager()
