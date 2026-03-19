from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class CustomerCreate(BaseModel):
    customer_id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    home_location: Optional[str] = None
    avg_transaction_amount: Optional[float] = 0.0
    avg_daily_transactions: Optional[float] = 0.0
    risk_level: Optional[str] = "LOW"


class CustomerResponse(BaseModel):
    id: int
    customer_id: str
    name: str
    email: str
    phone: Optional[str] = None
    home_location: Optional[str] = None
    avg_transaction_amount: float
    avg_daily_transactions: float
    total_transactions: int
    risk_level: str
    created_at: datetime

    class Config:
        from_attributes = True


class DeviceCreate(BaseModel):
    device_id: str
    customer_id: str
    device_type: Optional[str] = None
    browser: Optional[str] = None
    operating_system: Optional[str] = None
    ip_address: Optional[str] = None


class DeviceResponse(BaseModel):
    id: int
    device_id: str
    customer_id: str
    device_type: Optional[str] = None
    browser: Optional[str] = None
    operating_system: Optional[str] = None
    ip_address: Optional[str] = None
    first_seen: datetime
    last_used: datetime

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: int
    customer_id: str
    transaction_id: Optional[int] = None
    notification_type: str
    recipient: str
    subject: Optional[str] = None
    message: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
