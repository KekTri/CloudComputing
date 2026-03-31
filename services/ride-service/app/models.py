from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
import uuid


class RideStatus(str, Enum):
    PENDING = "PENDING"
    AWAITING_DRIVER = "AWAITING_DRIVER"
    DRIVER_ASSIGNED = "DRIVER_ASSIGNED"
    PAYMENT_AUTHORIZED = "PAYMENT_AUTHORIZED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Location(BaseModel):
    lat: float
    lon: float


class CreateRideRequest(BaseModel):
    customer_id: str
    pickup: Location
    dropoff: Location


class RideResponse(BaseModel):
    ride_id: str
    customer_id: str
    driver_id: Optional[str] = None
    pickup: Location
    dropoff: Location
    status: RideStatus
    price_eur: float
    estimated_duration_min: float
    distance_km: float
