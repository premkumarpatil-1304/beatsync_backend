from pydantic import BaseSettings

class Settings(BaseSettings):
    MAX_ROOM_USERS: int = 4
    WEBSOCKET_PING_INTERVAL: int = 20
    WEBSOCKET_PING_TIMEOUT: int = 20
    
    class Config:
        env_file = ".env"

settings = Settings()
