from pydantic import BaseModel
from typing import Optional
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    FAILED = "FAILED"
    CAPTURED = "CAPTURED"


class PaymentRecord(BaseModel):
    payment_id: str
    ride_id: str
    customer_id: str
    amount_eur: float
    status: PaymentStatus
