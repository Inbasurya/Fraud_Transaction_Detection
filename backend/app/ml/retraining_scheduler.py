"""Adaptive model retraining scheduler."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.behavior_models import behavior_model
from app.config import settings
from app.database import SessionLocal
from app.ml_models.kaggle_fraud_model import kaggle_model
from app.models.training_feedback_model import TrainingFeedback

logger = logging.getLogger(__name__)


class RetrainingScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self.last_run_at: datetime | None = None
        self.last_status = "idle"
        self.last_error: str | None = None
        self.last_new_labels = 0
        self.last_artifact_path: str | None = None

    def _feedback_dataset_path(self) -> Path:
        base_dir = Path(__file__).resolve().parents[2]
        return base_dir / "data" / "adaptive_training_feedback.csv"

    def _base_dataset_path(self) -> Path:
        return kaggle_model._resolve_data_path()

    def _new_labels_count(self) -> int:
        db = SessionLocal()
        try:
            query = db.query(TrainingFeedback)
            if self.last_run_at is not None:
                query = query.filter(TrainingFeedback.created_at > self.last_run_at)
            return int(query.count())
        finally:
            db.close()

    def _load_feedback_frame(self) -> pd.DataFrame:
        db = SessionLocal()
        try:
            rows = db.query(TrainingFeedback).order_by(TrainingFeedback.created_at.asc()).all()
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame([
                {
                    "transaction_id": f"FB-{row.id}",
                    "user_id": int(row.user_id),
                    "amount": float(row.amount or 0.0),
                    "merchant": row.merchant or "UNKNOWN",
                    "location": row.location or "UNKNOWN",
                    "device_type": row.device_type or "UNKNOWN",
                    "timestamp": row.timestamp.isoformat() if row.timestamp else datetime.now(timezone.utc).isoformat(),
                    "is_fraud": int(bool(row.is_fraud_label)),
                    "label_source": row.label_source or "analyst",
                }
                for row in rows
            ])
        finally:
            db.close()

    def _build_training_dataset(self) -> Path | None:
        feedback_df = self._load_feedback_frame()
        if feedback_df.empty:
            return None

        base_df = pd.read_csv(self._base_dataset_path())
        if {"Time", "Amount", "Class"}.issubset(base_df.columns):
            logger.info("Skipping adaptive dataset merge for Kaggle credit-card schema")
            return None

        merged = pd.concat([base_df, feedback_df], ignore_index=True, sort=False)
        target = self._feedback_dataset_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(target, index=False)
        self.last_artifact_path = str(target)
        return target

    def _should_retrain(self) -> bool:
        if not settings.MODEL_RETRAIN_ENABLED:
            return False
        now = datetime.now(timezone.utc)
        interval_elapsed = False
        if self.last_run_at is None:
            interval_elapsed = True
        else:
            elapsed = (now - self.last_run_at).total_seconds()
            interval_elapsed = elapsed >= (settings.MODEL_RETRAIN_INTERVAL_HOURS * 3600)

        self.last_new_labels = self._new_labels_count()
        enough_new_labels = self.last_new_labels >= settings.MODEL_RETRAIN_MIN_NEW_LABELS
        return interval_elapsed or enough_new_labels

    def retrain_now(self) -> dict[str, Any]:
        self.last_status = "running"
        dataset_path = self._build_training_dataset()
        payload: dict[str, Any] = {"scheduled": True, "new_labels": self.last_new_labels}
        try:
            payload["supervised"] = kaggle_model.retrain(str(dataset_path) if dataset_path else None)
            payload["behavior"] = behavior_model.retrain(str(dataset_path) if dataset_path else None)
            self.last_run_at = datetime.now(timezone.utc)
            self.last_status = "ok"
            self.last_error = None
            return payload
        except Exception as exc:
            self.last_status = "error"
            self.last_error = str(exc)
            logger.exception("Adaptive model retraining failed: %s", exc)
            raise

    async def _loop(self) -> None:
        while self._running:
            try:
                if self._should_retrain():
                    await asyncio.to_thread(self.retrain_now)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(60)

    async def start(self) -> None:
        if self._running or not settings.MODEL_RETRAIN_ENABLED:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="adaptive-retraining")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def stats(self) -> dict[str, Any]:
        return {
            "enabled": settings.MODEL_RETRAIN_ENABLED,
            "interval_hours": settings.MODEL_RETRAIN_INTERVAL_HOURS,
            "min_new_labels": settings.MODEL_RETRAIN_MIN_NEW_LABELS,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "new_labels_since_last_run": self.last_new_labels,
            "artifact_path": self.last_artifact_path,
            "running": bool(self._task and not self._task.done()),
        }


retraining_scheduler = RetrainingScheduler()
