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


app = FastAPI(title="Customer Service", lifespan=lifespan)


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


@app.get("/customers", response_model=list[CustomerResponse])
async def list_customers():
    db = get_db()
    customers = await db.customers.find().to_list(100)
    return [CustomerResponse(**{k: v for k, v in c.items() if k != "_id"}) for c in customers]


@app.delete("/customers/{customer_id}", status_code=204)
async def delete_customer(customer_id: str):
    db = get_db()
    result = await db.customers.delete_one({"customer_id": customer_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")


@app.get("/health")
async def health():
    return {"status": "ok"}
