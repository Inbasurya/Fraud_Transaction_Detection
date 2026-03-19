from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics.fraud_network_service import fraud_network_payload
from app.database import get_db

router = APIRouter()


@router.get("/fraud-network")
def fraud_network(limit: int = 2000, db: Session = Depends(get_db)):
    return fraud_network_payload(db, limit=limit)
