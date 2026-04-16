import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .database import connect_db, close_db, get_db
from .kafka_client import start_producer, stop_producer, publish, start_consumer
from .models import (
    CreateDriverRequest, DriverResponse, DriverStatus,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app_state: dict = {}


async def event_handler(topic: str, data: dict):
    db = get_db()

    if topic == "ride.created":
        ride_id = data.get("ride_id")
        # Find an available driver
        driver = await db.drivers.find_one({"status": DriverStatus.AVAILABLE})
        if driver:
            await db.drivers.update_one(
                {"driver_id": driver["driver_id"]},
                {"$set": {"status": DriverStatus.BUSY, "current_ride_id": ride_id}},
            )
            await publish("driver.assigned", {
                "ride_id": ride_id,
                "driver_id": driver["driver_id"],
            })
            logger.info(f"Driver {driver['driver_id']} assigned to ride {ride_id}")
        else:
            await publish("driver.assignment.failed", {
                "ride_id": ride_id,
                "reason": "No available drivers",
            })
            logger.info(f"No available driver for ride {ride_id} -> assignment failed")

    elif topic == "driver.release":
        driver_id = data.get("driver_id")
        if driver_id:
            await db.drivers.update_one(
                {"driver_id": driver_id},
                {"$set": {"status": DriverStatus.AVAILABLE, "current_ride_id": None}},
            )
            logger.info(f"Driver {driver_id} released (compensating transaction)")

    elif topic == "ride.completed":
        driver_id = data.get("driver_id")
        if driver_id:
            await db.drivers.update_one(
                {"driver_id": driver_id},
                {"$set": {"status": DriverStatus.AVAILABLE, "current_ride_id": None}},
            )
            logger.info(f"Driver {driver_id} freed after ride completion")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await start_producer()
    app_state["event_handler"] = event_handler
    consumer_task = asyncio.create_task(start_consumer(app_state))
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await stop_producer()
    await close_db()


app = FastAPI(title="Driver Service", lifespan=lifespan, docs_url="/drivers/docs", openapi_url="/drivers/openapi.json")


@app.post("/drivers", response_model=DriverResponse, status_code=201)
async def create_driver(body: CreateDriverRequest):
    db = get_db()
    driver_id = str(uuid.uuid4())
    doc = {
        "driver_id": driver_id,
        "name": body.name,
        "vehicle": body.vehicle,
        "status": DriverStatus.AVAILABLE,
        "current_location": body.current_location.model_dump(),
        "current_ride_id": None,
    }
    await db.drivers.insert_one(doc)
    return DriverResponse(**{k: v for k, v in doc.items() if k != "_id"})


@app.get("/drivers/{driver_id}", response_model=DriverResponse)
async def get_driver(driver_id: str):
    db = get_db()
    driver = await db.drivers.find_one({"driver_id": driver_id})
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return DriverResponse(**{k: v for k, v in driver.items() if k != "_id"})


@app.get("/health")
async def health():
    return {"status": "ok"}
