from pydantic import BaseModel
from datetime import datetime


class FraudPredictionResponse(BaseModel):
    id: int
    transaction_id: int
    fraud_probability: float
    risk_score: float
    risk_category: str
    model_used: str
    created_at: datetime

    class Config:
        from_attributes = True
