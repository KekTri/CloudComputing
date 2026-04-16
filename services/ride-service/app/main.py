import asyncio
import logging
import math
import os
import uuid
from contextlib import asynccontextmanager


from fastapi import FastAPI, HTTPException

from .database import connect_db, close_db, get_db
from .kafka_client import start_producer, stop_producer, publish, start_consumer
from .models import CreateRideRequest, RideResponse, RideStatus, Location

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app_state: dict = {}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line approximation: degree difference * 111 km/degree."""
    dlat = abs(lat2 - lat1)
    dlon = abs(lon2 - lon1)
    dist_deg = math.sqrt(dlat**2 + dlon**2)
    return dist_deg * 111.0


def compute_price(distance_km: float) -> float:
    return max(3.0, distance_km * 1.5)


def compute_duration_min(distance_km: float) -> float:
    """distance / 30 km/h -> hours -> * 60 -> minutes."""
    return (distance_km / 30.0) * 60.0


async def saga_event_handler(topic: str, data: dict):
    db = get_db()
    ride_id = data.get("ride_id")
    if not ride_id:
        return

    if topic == "driver.assigned":
        driver_id = data.get("driver_id")
        await db.rides.update_one(
            {"ride_id": ride_id, "status": RideStatus.AWAITING_DRIVER},
            {"$set": {"status": RideStatus.DRIVER_ASSIGNED, "driver_id": driver_id}},
        )
        ride = await db.rides.find_one({"ride_id": ride_id})
        if ride:
            await publish("payment.requested", {
                "ride_id": ride_id,
                "customer_id": ride["customer_id"],
                "amount_eur": ride["price_eur"],
            })
            logger.info(f"Ride {ride_id}: DRIVER_ASSIGNED -> payment.requested")

    elif topic == "driver.assignment.failed":
        await db.rides.update_one(
            {"ride_id": ride_id},
            {"$set": {"status": RideStatus.CANCELLED}},
        )
        logger.info(f"Ride {ride_id}: driver assignment failed -> CANCELLED")

    elif topic == "payment.authorized":
        await db.rides.update_one(
            {"ride_id": ride_id, "status": RideStatus.DRIVER_ASSIGNED},
            {"$set": {"status": RideStatus.PAYMENT_AUTHORIZED}},
        )
        logger.info(f"Ride {ride_id}: PAYMENT_AUTHORIZED -> ready for pickup")

    elif topic == "payment.failed":
        ride = await db.rides.find_one({"ride_id": ride_id})
        if ride and ride["status"] not in (RideStatus.CANCELLED, RideStatus.COMPLETED):
            await db.rides.update_one(
                {"ride_id": ride_id},
                {"$set": {"status": RideStatus.CANCELLED}},
            )
            await publish("driver.release", {
                "ride_id": ride_id,
                "driver_id": ride.get("driver_id"),
            })
            logger.info(f"Ride {ride_id}: payment failed -> CANCELLED + driver.release")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await start_producer()
    app_state["saga_handler"] = saga_event_handler
    consumer_task = asyncio.create_task(start_consumer(app_state))
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await stop_producer()
    await close_db()


app = FastAPI(title="Ride Service", lifespan=lifespan, docs_url="/rides/docs", openapi_url="/rides/openapi.json")


@app.post("/rides", response_model=RideResponse, status_code=201)
async def create_ride(body: CreateRideRequest):
    db = get_db()
    ride_id = str(uuid.uuid4())
    distance_km = haversine_km(
        body.pickup.lat, body.pickup.lon,
        body.dropoff.lat, body.dropoff.lon,
    )
    price = compute_price(distance_km)
    duration = compute_duration_min(distance_km)

    ride_doc = {
        "ride_id": ride_id,
        "customer_id": body.customer_id,
        "driver_id": None,
        "pickup": body.pickup.model_dump(),
        "dropoff": body.dropoff.model_dump(),
        "status": RideStatus.PENDING,
        "price_eur": price,
        "estimated_duration_min": duration,
        "distance_km": distance_km,
    }
    await db.rides.insert_one(ride_doc)

    # Transition to AWAITING_DRIVER and publish ride.created
    await db.rides.update_one(
        {"ride_id": ride_id},
        {"$set": {"status": RideStatus.AWAITING_DRIVER}},
    )
    await publish("ride.created", {
        "ride_id": ride_id,
        "customer_id": body.customer_id,
        "pickup": body.pickup.model_dump(),
        "dropoff": body.dropoff.model_dump(),
        "price_eur": price,
    })
    logger.info(f"Ride {ride_id} created -> ride.created published")

    ride_doc["status"] = RideStatus.AWAITING_DRIVER
    return RideResponse(**{k: v for k, v in ride_doc.items() if k != "_id"})


@app.get("/rides/{ride_id}", response_model=RideResponse)
async def get_ride(ride_id: str):
    db = get_db()
    ride = await db.rides.find_one({"ride_id": ride_id})
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return RideResponse(**{k: v for k, v in ride.items() if k != "_id"})


@app.post("/rides/{ride_id}/start")
async def start_ride(ride_id: str):
    db = get_db()
    result = await db.rides.update_one(
        {"ride_id": ride_id, "status": RideStatus.PAYMENT_AUTHORIZED},
        {"$set": {"status": RideStatus.ACTIVE}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=400, detail="Ride not in PAYMENT_AUTHORIZED state")
    await publish("ride.started", {"ride_id": ride_id})
    return {"ride_id": ride_id, "status": RideStatus.ACTIVE}


@app.post("/rides/{ride_id}/complete")
async def complete_ride(ride_id: str):
    db = get_db()
    ride = await db.rides.find_one({"ride_id": ride_id})
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride["status"] != RideStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Ride not ACTIVE")
    await db.rides.update_one(
        {"ride_id": ride_id},
        {"$set": {"status": RideStatus.COMPLETED}},
    )
    await publish("ride.completed", {
        "ride_id": ride_id,
        "driver_id": ride.get("driver_id"),
        "customer_id": ride["customer_id"],
        "price_eur": ride["price_eur"],
    })
    return {"ride_id": ride_id, "status": RideStatus.COMPLETED}


@app.get("/health")
async def health():
    return {"status": "ok"}
