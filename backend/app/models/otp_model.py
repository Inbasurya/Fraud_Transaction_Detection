"""OTP attempts tracking model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base


class OTPAttempt(Base):
    __tablename__ = "otp_attempts"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, index=True, nullable=False)
    customer_id = Column(String, index=True, nullable=False)
    otp_hash = Column(String, nullable=False)
    channel = Column(String, nullable=False)  # sms / email
    recipient = Column(String, nullable=False)
    verified = Column(Boolean, default=False)
    attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
    expired = Column(Boolean, default=False)
