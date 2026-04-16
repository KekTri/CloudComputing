import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from .database import connect_db, close_db, get_db
from .kafka_client import start_producer, stop_producer, publish
from .models import PositionUpdateRequest, PositionRecord

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await start_producer()
    yield
    await stop_producer()
    await close_db()


app = FastAPI(title="Tracking Service", lifespan=lifespan, docs_url="/tracking/docs", openapi_url="/tracking/openapi.json")


@app.post("/tracking/position")
async def update_position(body: PositionUpdateRequest):
    db = get_db()
    ts = datetime.now(timezone.utc).isoformat()
    doc = {
        "ride_id": body.ride_id,
        "driver_id": body.driver_id,
        "lat": body.lat,
        "lon": body.lon,
        "timestamp": ts,
    }
    await db.positions.insert_one(doc)
    await publish("position.updated", doc)
    return {"status": "ok", "timestamp": ts}


@app.get("/tracking/{ride_id}/latest", response_model=PositionRecord)
async def get_latest_position(ride_id: str):
    db = get_db()
    positions = await db.positions.find(
        {"ride_id": ride_id}
    ).sort("timestamp", -1).limit(1).to_list(1)
    if not positions:
        raise HTTPException(status_code=404, detail="No position data for this ride")
    p = positions[0]
    return PositionRecord(**{k: v for k, v in p.items() if k != "_id"})


@app.get("/health")
async def health():
    return {"status": "ok"}
