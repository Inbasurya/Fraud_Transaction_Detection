"""Customer intelligence model for behavioral profiling."""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    home_location = Column(String, nullable=True)
    avg_transaction_amount = Column(Float, default=0.0)
    avg_daily_transactions = Column(Float, default=0.0)
    total_transactions = Column(Integer, default=0)
    risk_level = Column(String, default="LOW")  # LOW / MEDIUM / HIGH
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    devices = relationship("Device", back_populates="customer")
    notifications = relationship("Notification", back_populates="customer")
