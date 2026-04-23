from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from schemas import CreateRoomRequest, JoinRoomRequest, PlaybackControl, UploadUrlRequest
from room_manager import room_manager
from websocket_manager import manager
from utils import generate_user_id, format_room_state, get_live_time
from datetime import datetime
import os
import shutil
import asyncio
from pathlib import Path
import yt_dlp

app = FastAPI(title="BeatSync API", version="1.0.0")

# Create uploads directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
app.mount("/audio", StaticFiles(directory=str(UPLOAD_DIR)), name="audio")

@app.get("/")
async def root():
    return {"message": "BeatSync API is running"}

@app.post("/room/create")
async def create_room(request: CreateRoomRequest):
    user_id = generate_user_id()
    room = room_manager.create_room(user_id, request.username)
    
    return {
        "room_id": room.room_id,
        "user_id": user_id,
        "message": "Room created successfully"
    }

@app.post("/room/join")
async def join_room(request: JoinRoomRequest):
    room = room_manager.get_room(request.room_id)
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if len(room.users) >= 4:
        raise HTTPException(status_code=400, detail="Room is full")
    
    user_id = generate_user_id()
    room = room_manager.join_room(request.room_id, user_id, request.username)
    
    return {
        "room_id": room.room_id,
        "user_id": user_id,
        "message": "Joined room successfully"
    }

@app.get("/room/{room_id}")
async def get_room_info(room_id: str):
    room = room_manager.get_room(room_id)
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    return format_room_state(room)

@app.post("/upload-music/{room_id}")
async def upload_music(room_id: str, file: UploadFile = File(...)):
    """Upload music file and broadcast to all users in the room"""
    room = room_manager.get_room(room_id)
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Validate file type
    allowed_extensions = [".mp3", ".wav", ".ogg", ".m4a"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Save file with unique name
    file_id = generate_user_id()[:8]
    safe_filename = f"{file_id}{file_ext}"
    file_path = UPLOAD_DIR / safe_filename
    
    # Save uploaded file
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create audio URL
    audio_url = f"/audio/{safe_filename}"
    
    # Update room with new track
    room.current_track = audio_url
    room.is_playing = False
    room.current_time = 0.0
    
    # Broadcast to all users in the room
    await manager.broadcast_to_room({
        "type": "new_track",
        "data": {
            "track_url": audio_url,
            "filename": file.filename,
            "message": "New music uploaded!"
        }
    }, room_id)
    
    return {
        "message": "Music uploaded successfully",
        "audio_url": audio_url,
        "filename": file.filename
    }

def download_audio_from_url(url: str, output_dir: Path) -> dict:
    file_id = generate_user_id()[:8]
    # Prefer m4a or webm which play nicely in browsers natively
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio',
        'outtmpl': f'{output_dir}/{file_id}.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        # Getting actual extension downloaded
        filename = ydl.prepare_filename(info_dict)
        return {
            "filename": os.path.basename(filename),
            "title": info_dict.get('title', 'Unknown Title')
        }

@app.post("/upload-url/{room_id}")
async def upload_url(room_id: str, request: UploadUrlRequest):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
        
    try:
        # Run yt-dlp in a separate thread so it doesn't block the async event loop
        result = await asyncio.to_thread(download_audio_from_url, request.url, UPLOAD_DIR)
        
        safe_filename = result["filename"]
        track_title = result["title"]
        audio_url = f"/audio/{safe_filename}"
        
        room.current_track = audio_url
        room.is_playing = False
        room.current_time = 0.0
        
        await manager.broadcast_to_room({
            "type": "new_track",
            "data": {
                "track_url": audio_url,
                "filename": track_title,
                "message": "New music URL loaded!"
            }
        }, room_id)
        
        return {
            "message": "URL music added successfully",
            "audio_url": audio_url,
            "filename": track_title
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.websocket("/ws/{room_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, user_id: str):
    room = room_manager.get_room(room_id)
    
    if not room or user_id not in room.users:
        await websocket.close(code=1008)
        return
    
    await manager.connect(room_id, user_id, websocket)
    
    # Send current state to newly connected user
    await manager.send_personal_message({
        "type": "state",
        "data": format_room_state(room)
    }, room_id, user_id)
    
    # Notify others about new user
    await manager.broadcast_to_room({
        "type": "user_joined",
        "data": {
            "user_id": user_id,
            "username": room.users[user_id].username,
            "users_count": len(room.users)
        }
    }, room_id, exclude_user=user_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "play":
                room.is_playing = True
                room.current_time = data.get("current_time", 0.0)
                room.last_update = datetime.now()

                if data.get("track_url"):
                    room.current_track = data["track_url"]

                await manager.broadcast_to_room({
                    "type": "play",
                    "data": {
                        "current_track": room.current_track,
                        "current_time": room.current_time,  # exact time client sent
                        "timestamp": room.last_update.isoformat()
                    }
                }, room_id)
            
            elif message_type == "pause":
                # Use the client-reported live time; fall back to our computed
                # position if the client didn't send one (shouldn't happen).
                live_at_pause = data.get("current_time", get_live_time(room))
                room.is_playing = False
                room.current_time = live_at_pause
                room.last_update = datetime.now()

                await manager.broadcast_to_room({
                    "type": "pause",
                    "data": {
                        "current_time": room.current_time
                    }
                }, room_id)
            
            elif message_type == "seek":
                room.current_time = data.get("current_time", 0.0)
                room.last_update = datetime.now()

                await manager.broadcast_to_room({
                    "type": "seek",
                    "data": {
                        "current_time": room.current_time,
                        "is_playing": room.is_playing
                    }
                }, room_id)
            
            elif message_type == "sync_request":
                await manager.send_personal_message({
                    "type": "sync_response",
                    "data": {
                        "current_track": room.current_track,
                        "is_playing": room.is_playing,
                        "current_time": get_live_time(room),  # real position
                        "last_update": room.last_update.isoformat()
                    }
                }, room_id, user_id)
                
            elif message_type == "chat":
                await manager.broadcast_to_room({
                    "type": "chat",
                    "data": {
                        "user_id": user_id,
                        "username": room.users[user_id].username,
                        "message": data.get("message"),
                        "timestamp": datetime.now().isoformat()
                    }
                }, room_id)
                
            elif message_type == "reaction":
                await manager.broadcast_to_room({
                    "type": "reaction",
                    "data": {
                        "user_id": user_id,
                        "username": room.users[user_id].username,
                        "emoji": data.get("emoji")
                    }
                }, room_id)
    
    except WebSocketDisconnect:
        manager.disconnect(room_id, user_id)
        room_manager.leave_room(room_id, user_id)
        
        await manager.broadcast_to_room({
            "type": "user_left",
            "data": {
                "user_id": user_id,
                "users_count": len(room.users) if room_manager.get_room(room_id) else 0
            }
        }, room_id)

        

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
