from pydantic import BaseModel
from datetime import datetime


class AlertResponse(BaseModel):
    id: int
    transaction_id: int
    risk_score: float
    alert_type: str
    status: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True
