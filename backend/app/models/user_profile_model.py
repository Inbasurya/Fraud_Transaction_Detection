"""User behavior profile model for tracking spending patterns."""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime
from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False)
    avg_transaction_amount = Column(Float, default=0.0)
    avg_daily_transactions = Column(Float, default=0.0)
    total_transactions = Column(Integer, default=0)
    last_location = Column(String, nullable=True)
    last_device = Column(String, nullable=True)
    last_merchant = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
