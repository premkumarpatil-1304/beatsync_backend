from typing import Dict, Optional
from datetime import datetime
from models import Room, User
from config import settings
import uuid

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def create_room(self, host_id: str, username: str) -> Room:
        room_id = str(uuid.uuid4())[:8]
        host = User(user_id=host_id, username=username, is_host=True)
        
        room = Room(
            room_id=room_id,
            host_id=host_id,
            users={host_id: host}
        )
        self.rooms[room_id] = room
        return room

    def get_room(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    def join_room(self, room_id: str, user_id: str, username: str) -> Optional[Room]:
        room = self.rooms.get(room_id)
        if not room or len(room.users) >= settings.MAX_ROOM_USERS:
            return None
        
        user = User(user_id=user_id, username=username)
        room.add_user(user)
        return room

    def leave_room(self, room_id: str, user_id: str) -> None:
        room = self.rooms.get(room_id)
        if not room:
            return

        room.remove_user(user_id)

        if not room.users:
            del self.rooms[room_id]
        elif user_id == room.host_id:
            new_host_id = next(iter(room.users))
            room.host_id = new_host_id
            room.users[new_host_id].is_host = True

    def update_playback(self, room_id: str, track_url: Optional[str],
                        is_playing: bool, current_time: float) -> None:
        room = self.rooms.get(room_id)
        if room:
            if track_url:
                room.current_track = track_url
            room.is_playing = is_playing
            room.current_time = current_time
            room.last_update = datetime.now()

room_manager = RoomManager()
 