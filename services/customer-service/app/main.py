import os
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .database import connect_db, close_db, get_db
from .models import CreateCustomerRequest, CustomerResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(title="Customer Service", lifespan=lifespan, docs_url="/customers/docs", openapi_url="/customers/openapi.json")


@app.post("/customers", response_model=CustomerResponse, status_code=201)
async def create_customer(body: CreateCustomerRequest):
    db = get_db()
    customer_id = str(uuid.uuid4())
    doc = {
        "customer_id": customer_id,
        "name": body.name,
        "email": body.email,
        "phone": body.phone,
    }
    await db.customers.insert_one(doc)
    return CustomerResponse(**{k: v for k, v in doc.items() if k != "_id"})


@app.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: str):
    db = get_db()
    customer = await db.customers.find_one({"customer_id": customer_id})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse(**{k: v for k, v in customer.items() if k != "_id"})



@app.get("/health")
async def health():
    return {"status": "ok"}
