from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class TrainingFeedback(Base):
    __tablename__ = "training_feedback"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    merchant = Column(String)
    location = Column(String)
    device_type = Column(String)
    timestamp = Column(DateTime, nullable=False)
    is_fraud_label = Column(Boolean, nullable=False)
    label_source = Column(String, default="analyst")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction = relationship("Transaction")
