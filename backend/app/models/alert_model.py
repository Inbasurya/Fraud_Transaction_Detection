import uuid
from datetime import datetime
from sqlalchemy import Column, Float, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False)
    risk_score = Column(Float, nullable=False)
    alert_type = Column(String, nullable=False)  # USER_ALERT / ADMIN_ALERT
    status = Column(String, default="OPEN")  # OPEN / CLOSED
    message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    transaction = relationship("Transaction", back_populates="alerts")
