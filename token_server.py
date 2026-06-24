import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants

load_dotenv()

LIVEKIT_API_KEY = os.environ["LIVEKIT_API_KEY"]
LIVEKIT_API_SECRET = os.environ["LIVEKIT_API_SECRET"]
LIVEKIT_URL = os.environ["LIVEKIT_URL"]

app = FastAPI(title="Restaurant Token Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/token")
async def get_token(room: str = None, identity: str = None):
    room_name = room or f"restaurant-{uuid.uuid4().hex[:8]}"
    user_identity = identity or f"user-{uuid.uuid4().hex[:8]}"

    try:
        token = (
            AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(user_identity)
            .with_name("Customer")
            .with_grants(VideoGrants(room_join=True, room=room_name))
            .to_jwt()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "token": token,
        "url": LIVEKIT_URL,
        "room": room_name,
        "identity": user_identity,
    }
