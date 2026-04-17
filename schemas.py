from pydantic import BaseModel
from typing import Optional

class CreateRoomRequest(BaseModel):
    username: str

class JoinRoomRequest(BaseModel):
    room_id: str
    username: str

class UploadUrlRequest(BaseModel):
    url: str

class PlaybackControl(BaseModel):
    action: str  # play, pause, seek
    track_url: Optional[str] = None
    timestamp: Optional[float] = None

class SyncState(BaseModel):
    room_id: str
    current_track: Optional[str]
    is_playing: bool
    current_time: float
    users_count: int
