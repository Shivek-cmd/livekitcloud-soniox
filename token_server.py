import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants, LiveKitAPI, CreateAgentDispatchRequest
from pydantic import BaseModel, Field

from restaurant import menu_provider
from restaurant.store_checkout import place_store_order, validate_store_checkout
from restaurant.store_rate_limit import allow_store_checkout

load_dotenv()

LIVEKIT_API_KEY = os.environ["LIVEKIT_API_KEY"]
LIVEKIT_API_SECRET = os.environ["LIVEKIT_API_SECRET"]
LIVEKIT_URL = os.environ["LIVEKIT_URL"]

app = FastAPI(title="Restaurant Token Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class StoreCheckoutCustomer(BaseModel):
    name: str = ""
    phone: str = ""


class StoreCheckoutItem(BaseModel):
    id: str
    qty: int = 1
    modifiers: list[str] = Field(default_factory=list)


class StoreCheckoutRequest(BaseModel):
    items: list[StoreCheckoutItem] = Field(default_factory=list)
    order_type: str = ""
    customer: StoreCheckoutCustomer = Field(default_factory=StoreCheckoutCustomer)
    delivery_address: str | None = None
    note: str | None = None
    place: bool = False


def _client_key(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/menu")
async def get_menu():
    """Full menu catalog (grouped by category) for the web menu panel."""
    catalog = menu_provider.catalog()
    if catalog is None:
        raise HTTPException(status_code=503, detail="Menu is not available")
    return catalog


@app.post("/store/checkout")
async def store_checkout(body: StoreCheckoutRequest, request: Request):
    """Validate Store checkout; place when place=True (S4). Rate-limited (S5)."""
    if not allow_store_checkout(_client_key(request)):
        raise HTTPException(
            status_code=429,
            detail={
                "ok": False,
                "status": "rate_limited",
                "blockers": [
                    "Too many checkout attempts. Please wait a minute and try again."
                ],
            },
        )

    payload = body.model_dump()
    if body.place:
        result = await place_store_order(payload)
    else:
        result = validate_store_checkout(payload)

    if not result.ok:
        status = 400
        if body.place and result.summary and result.blockers and any(
            "kitchen" in b.lower() or "pos" in b.lower() for b in result.blockers
        ):
            status = 502
        raise HTTPException(status_code=status, detail=result.to_dict())

    out = result.to_dict()
    out["place_requested"] = bool(body.place)
    out["placed"] = bool(result.summary and result.summary.get("placed"))
    return out


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

    try:
        async with LiveKitAPI(
            url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
        ) as lk:
            await lk.agent_dispatch.create_dispatch(
                CreateAgentDispatchRequest(
                    room=room_name,
                    agent_name=os.getenv("AGENT_NAME", "restaurant-agent"),
                )
            )
    except Exception:
        pass

    return {
        "token": token,
        "url": LIVEKIT_URL,
        "room": room_name,
        "identity": user_identity,
    }
