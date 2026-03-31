from pydantic import BaseModel
from typing import Optional


class CreateCustomerRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None


class CustomerResponse(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: Optional[str] = None
