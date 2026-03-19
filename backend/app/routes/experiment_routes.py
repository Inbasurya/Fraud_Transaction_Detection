from fastapi import APIRouter

from app.analytics.experiment_tracker import experiment_tracker

router = APIRouter()


@router.get("/experiments/metrics")
def experiment_metrics():
    return experiment_tracker.payload()
