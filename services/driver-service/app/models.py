from pydantic import BaseModel
from typing import Optional
from enum import Enum


class DriverStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class Location(BaseModel):
    lat: float
    lon: float


class CreateDriverRequest(BaseModel):
    name: str
    vehicle: str
    current_location: Location


class DriverResponse(BaseModel):
    driver_id: str
    name: str
    vehicle: str
    status: DriverStatus
    current_location: Location
    current_ride_id: Optional[str] = None


class UpdateLocationRequest(BaseModel):
    lat: float
    lon: float
