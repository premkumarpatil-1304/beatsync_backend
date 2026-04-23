import uuid
from typing import Dict
from datetime import datetime

def generate_user_id() -> str:
    return uuid.uuid4().hex  # shorter ID, no dashes

def get_live_time(room) -> float:
    """
    Returns the real playback position in seconds.

    If the room is currently playing, we add the elapsed wall-clock seconds
    since the last update to the stored position — so callers always get an
    accurate current time without the backend needing a running timer.
    """
    if room.is_playing and room.last_update:
        elapsed = (datetime.now() - room.last_update).total_seconds()
        return round(room.current_time + elapsed, 3)
    return round(room.current_time, 3)

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
        "current_time": get_live_time(room),   # always the real position
        "users_count": len(room.users)
    }
