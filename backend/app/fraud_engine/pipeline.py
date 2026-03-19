"""Real-time fraud pipeline orchestration."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from app.fraud_engine.hybrid_engine import score_transaction


async def run_realtime_pipeline(db: Session, transaction: Any) -> dict[str, Any]:
    """Transaction stream -> features -> models -> rules -> risk score."""
    return await score_transaction(db, transaction)
