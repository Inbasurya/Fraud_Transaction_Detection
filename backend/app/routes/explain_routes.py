from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import transaction_model
from app.core.features import build_features
from app.services.explain_service import explain_transaction_by_record
from app.ml_models.kaggle_fraud_model import kaggle_model

router = APIRouter()


@router.get("/explain/{transaction_id}")
def explain(transaction_id: str, db: Session = Depends(get_db)):
    """Return SHAP-style explanation for a transaction (no auth for dashboard)."""
    tx = db.query(transaction_model.Transaction).filter(
        transaction_model.Transaction.transaction_id == transaction_id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    features = build_features(db, tx)
    payload = explain_transaction_by_record(tx, tx.prediction, features)
    shap_details = kaggle_model.shap_explanation(features)
    payload["shap_values"] = shap_details.get("shap_values", {})
    payload["feature_contributions"] = shap_details.get("top_features", [])
    payload["fraud_reasoning"] = payload.get("reasons", [])
    return payload
