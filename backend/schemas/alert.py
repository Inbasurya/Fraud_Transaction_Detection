"""Pydantic schemas for alerts."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: UUID
    transaction_id: UUID
    customer_id: str
    alert_type: Optional[str]
    severity: Optional[str]
    title: Optional[str]
    description: Optional[str]
    status: str
    assigned_to: Optional[str]
    resolved_at: Optional[datetime]
    resolution: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None


class AlertList(BaseModel):
    alerts: List[AlertResponse]
    total: int
