"""Model intelligence routes for SOC dashboard."""

from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.fraud_engine.hybrid_engine import model_metrics_payload
from app.ml_models.kaggle_fraud_model import kaggle_model
from app.behavior_models import behavior_model
from app.ml.retraining_scheduler import retraining_scheduler
from app.database import get_db
from app.analytics.model_health import model_health_payload

router = APIRouter()


class RetrainRequest(BaseModel):
    model_type: str = "all"


class UploadDatasetRequest(BaseModel):
    model_type: str = "supervised"
    filename: str = "uploaded_dataset.csv"
    csv_content: str


@router.get("/metrics")
def get_model_metrics():
    try:
        payload = model_metrics_payload()
        payload["adaptive_retraining"] = retraining_scheduler.stats()
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load model metrics: {exc}") from exc


@router.get("/health")
def get_model_health(db: Session = Depends(get_db)):
    try:
        return model_health_payload(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to compute model health: {exc}") from exc


@router.post("/train")
def retrain_models(payload: RetrainRequest):
    """Retrain supervised and/or behavioral models."""
    try:
        model_type = payload.model_type
        payload: dict = {"status": "ok"}
        if model_type in ("all", "supervised"):
            payload["supervised"] = kaggle_model.retrain()
        if model_type in ("all", "behavior"):
            payload["behavior"] = behavior_model.retrain()
        payload["metrics"] = model_metrics_payload()
        payload["adaptive_retraining"] = retraining_scheduler.stats()
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model retraining failed: {exc}") from exc


@router.post("/upload-dataset")
def upload_dataset(payload: UploadDatasetRequest):
    """Upload model training dataset and retrain selected model."""
    try:
        data_dir = Path(__file__).resolve().parents[2] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        target = data_dir / payload.filename
        target.write_text(payload.csv_content, encoding="utf-8")

        if payload.model_type == "behavior":
            metrics = behavior_model.retrain(str(target))
        else:
            metrics = kaggle_model.retrain(str(target))

        return {
            "status": "uploaded",
            "model_type": payload.model_type,
            "dataset_path": str(target),
            "metrics": metrics,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dataset upload failed: {exc}") from exc
