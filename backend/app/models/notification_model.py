"""Notification log model for tracking sent SMS/email alerts."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False, index=True)
    transaction_id = Column(Integer, nullable=True)
    notification_type = Column(String, nullable=False)  # SMS / EMAIL
    recipient = Column(String, nullable=False)  # phone or email
    subject = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    status = Column(String, default="SENT")  # SENT / FAILED / PENDING
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="notifications")
