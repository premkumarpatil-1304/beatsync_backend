from typing import Dict
from fastapi import WebSocket
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, room_id: str, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(room_id, {})[user_id] = websocket

    def disconnect(self, room_id: str, user_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].pop(user_id, None)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def send_personal_message(self, message: dict, room_id: str, user_id: str):
        if room_id in self.active_connections:
            websocket = self.active_connections[room_id].get(user_id)
            if websocket:
                await websocket.send_json(message)

    async def broadcast_to_room(self, message: dict, room_id: str, exclude_user: str = None):
        if room_id in self.active_connections:
            tasks = []
            for user_id, connection in self.active_connections[room_id].items():
                if exclude_user and user_id == exclude_user:
                    continue
                try:
                    tasks.append(connection.send_json(message))
                except Exception as e:
                    print(f"Error sending to {user_id}: {e}")
                    self.disconnect(room_id, user_id)
            await asyncio.gather(*tasks, return_exceptions=True)


manager = ConnectionManager()
