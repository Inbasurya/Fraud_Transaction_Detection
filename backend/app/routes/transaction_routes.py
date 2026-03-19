from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas import transaction_schema
from app.utils.auth_handler import get_current_user
from app.database import get_db
from app.services import fraud_service, audit_service
from app.streaming.engine import streaming_engine
from app.core.limiter import limiter

router = APIRouter()


@router.post("/score", response_model=transaction_schema.TransactionResponse)
@limiter.limit("100/minute")
async def score_transaction(
    request: Request,
    tx: transaction_schema.TransactionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Real-time fraud scoring endpoint with rate limiting and audit logging.
    Used by payment gateways and merchants for pre-auth checks.
    """
    # Create transaction record
    db_tx = fraud_service.create_transaction(db, tx)
    
    # Process synchronously for immediate response (bypassing queue for scoring API)
    payload = await fraud_service.process_transaction(db, db_tx)
    
    # Log audit event
    audit_event = {
        "txn_id": payload.get("transaction_id"),
        "customer_id": payload.get("user_id"),
        "amount": payload.get("amount"),
        "merchant": payload.get("merchant"),
        "risk_score": payload.get("risk_score"),
        "decision": payload.get("risk_category"),
        "top_features": payload.get("top_features", []),
        "explanation": payload.get("explanation", ""),
        "component_scores": payload.get("component_scores", {}),
        "processing_ms": payload.get("processing_time_ms", 0),
        "rules_triggered": payload.get("rules_triggered", []),
        "behavioral_score": payload.get("behavioral_score", 0),
        "ip_address": request.client.host,
        "device_id": payload.get("device_id", ""),
        "city": payload.get("location", ""), 
    }
    await audit_service.log_audit_event(audit_event)

    # broadcast over WebSocket
    await fraud_service.broadcast_transaction(payload)
    if payload.get("risk_category") in ("FRAUD", "SUSPICIOUS") and payload.get("alert_id"):
        await fraud_service.broadcast_alert(payload)

    return payload


@router.post("/", response_model=transaction_schema.TransactionResponse)
async def create_transaction(
    tx: transaction_schema.TransactionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a transaction and process it through producer-consumer pipeline."""
    db_tx = fraud_service.create_transaction(db, tx)
    payload = await streaming_engine.submit(db_tx.id)

    # broadcast over WebSocket
    await fraud_service.broadcast_transaction(payload)
    if payload.get("risk_category") in ("FRAUD", "SUSPICIOUS") and payload.get("alert_id"):
        await fraud_service.broadcast_alert(payload)

    return payload


@router.post("/simulate")
async def simulate_transaction(
    tx: transaction_schema.TransactionCreate,
    db: Session = Depends(get_db),
):
    """Simulator endpoint — no auth required so the streaming simulator can push."""
    db_tx = fraud_service.create_transaction(db, tx)
    payload = await fraud_service.process_transaction(db, db_tx)

    await fraud_service.broadcast_transaction(payload)
    if payload.get("risk_category") in ("FRAUD", "SUSPICIOUS") and payload.get("alert_id"):
        await fraud_service.broadcast_alert(payload)

    return payload


@router.get("/", response_model=List[transaction_schema.TransactionResponse])
def list_transactions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    txs = fraud_service.get_transactions(db, skip=skip, limit=limit)
    results = []
    for tx in txs:
        record = {
            "id": tx.id,
            "transaction_id": tx.transaction_id,
            "user_id": tx.user_id,
            "amount": tx.amount,
            "merchant": tx.merchant,
            "location": tx.location,
            "device_type": tx.device_type,
            "timestamp": tx.timestamp,
            "created_at": tx.created_at,
        }
        if tx.prediction:
            record.update({
                "fraud_probability": tx.prediction.fraud_probability,
                "risk_score": tx.prediction.risk_score,
                "risk_category": tx.prediction.risk_category,
            })
        results.append(record)
    return results
