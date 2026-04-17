from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class User(BaseModel):
    user_id: str
    username: str
    is_host: bool = False

class Room(BaseModel):
    room_id: str
    host_id: str
    users: Dict[str, User] = Field(default_factory=dict)

    current_track: Optional[str] = None
    is_playing: bool = False
    current_time: float = 0.0
    last_update: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    
    def add_user(self, user: User) -> bool:
        if len(self.users) >= 4:
            return False
        self.users[user.user_id] = user
        return True
    
    def remove_user(self, user_id: str) -> None:
        if user_id in self.users:
            del self.users[user_id]
