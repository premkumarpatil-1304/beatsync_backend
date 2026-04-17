import uuid
from typing import Dict

def generate_user_id() -> str:
    return uuid.uuid4().hex  # shorter ID, no dashes

def format_room_state(room) -> dict:
    return {
        "room_id": room.room_id,
        "host_id": room.host_id,
        "users": [
            {
                "user_id": user.user_id,
                "username": user.username,
                "is_host": user.is_host
            }
            for user in room.users.values()
        ],
        "current_track": room.current_track,
        "is_playing": room.is_playing,
        "current_time": room.current_time,
        "users_count": len(room.users)
    }
