"""Drift report model for storing data drift detection results."""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, JSON
from app.database import Base


class DriftReport(Base):
    __tablename__ = "drift_reports"

    id = Column(Integer, primary_key=True, index=True)
    drift_score = Column(Float, nullable=False)
    drift_detected = Column(Boolean, default=False)
    method = Column(String, default="evidently")
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
