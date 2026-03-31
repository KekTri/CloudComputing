from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PositionUpdateRequest(BaseModel):
    ride_id: str
    driver_id: str
    lat: float
    lon: float


class PositionRecord(BaseModel):
    ride_id: str
    driver_id: str
    lat: float
    lon: float
    timestamp: str
