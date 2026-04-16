import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .database import connect_db, close_db, get_db
from .kafka_client import start_producer, stop_producer, publish, start_consumer
from .models import PaymentRecord, PaymentStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app_state: dict = {}


async def payment_handler(data: dict):
    """
    Consumes payment.requested.
    Always authorizes (returns true per requirements).
    Publishes payment.authorized.
    """
    db = get_db()
    ride_id = data.get("ride_id")
    customer_id = data.get("customer_id")
    amount_eur = data.get("amount_eur", 0.0)

    payment_id = str(uuid.uuid4())
    doc = {
        "payment_id": payment_id,
        "ride_id": ride_id,
        "customer_id": customer_id,
        "amount_eur": amount_eur,
        "status": PaymentStatus.AUTHORIZED,
    }
    await db.payments.insert_one(doc)

    # Always succeeds per project requirements
    await publish("payment.authorized", {
        "ride_id": ride_id,
        "payment_id": payment_id,
        "amount_eur": amount_eur,
    })
    logger.info(f"Payment {payment_id} authorized for ride {ride_id}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await start_producer()
    app_state["payment_handler"] = payment_handler
    consumer_task = asyncio.create_task(start_consumer(app_state))
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await stop_producer()
    await close_db()


app = FastAPI(title="Payment Service", lifespan=lifespan, docs_url="/payments/docs", openapi_url="/payments/openapi.json")


@app.get("/payments/{ride_id}", response_model=PaymentRecord)
async def get_payment_by_ride(ride_id: str):
    db = get_db()
    payment = await db.payments.find_one({"ride_id": ride_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentRecord(**{k: v for k, v in payment.items() if k != "_id"})



@app.get("/health")
async def health():
    return {"status": "ok"}
