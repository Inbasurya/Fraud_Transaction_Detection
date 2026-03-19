"""
Model drift detector — monitors prediction distribution in real-time.
When fraud patterns shift (new attack types), this alerts before
the model degrades significantly.

Uses Population Stability Index (PSI) — the same metric used by
HDFC and SBI's model risk management teams.
"""
import json
import time
import numpy as np
import redis.asyncio as aioredis
from typing import Optional

class DriftDetector:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.BASELINE_WINDOW = 7 * 86400   # 7 days baseline
        self.CURRENT_WINDOW = 1 * 86400    # 1 day current
        self.PSI_WARNING = 0.1
        self.PSI_CRITICAL = 0.2

    async def record_prediction(self, risk_score: float, actual_fraud: Optional[bool] = None):
        """Record every prediction score for drift monitoring."""
        now = time.time()
        await self.redis.zadd(
            "drift:predictions",
            {f"{risk_score}:{now}": now}
        )
        await self.redis.zremrangebyscore(
            "drift:predictions", 0, now - self.BASELINE_WINDOW
        )

        if actual_fraud is not None:
            # Store labeled outcome for calibration
            await self.redis.zadd(
                "drift:labeled",
                {f"{risk_score}:{int(actual_fraud)}:{now}": now}
            )

    async def compute_psi(self) -> dict:
        """
        Population Stability Index — measures distribution shift.
        PSI < 0.1: No drift
        PSI 0.1-0.2: Moderate drift — monitor
        PSI > 0.2: Significant drift — retrain model
        """
        now = time.time()

        baseline_raw = await self.redis.zrangebyscore(
            "drift:predictions",
            now - self.BASELINE_WINDOW,
            now - self.CURRENT_WINDOW
        )
        current_raw = await self.redis.zrangebyscore(
            "drift:predictions",
            now - self.CURRENT_WINDOW,
            now
        )

        if len(baseline_raw) < 100 or len(current_raw) < 20:
            return {"psi": 0.0, "status": "insufficient_data", "n_baseline": len(baseline_raw), "n_current": len(current_raw)}

        baseline_scores = [float(r.decode().split(":")[0]) for r in baseline_raw]
        current_scores = [float(r.decode().split(":")[0]) for r in current_raw]

        bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        baseline_hist, _ = np.histogram(baseline_scores, bins=bins)
        current_hist, _ = np.histogram(current_scores, bins=bins)

        baseline_pct = baseline_hist / len(baseline_scores)
        current_pct = current_hist / len(current_scores)

        # PSI formula
        epsilon = 1e-10
        psi = sum(
            (c - b) * np.log((c + epsilon) / (b + epsilon))
            for b, c in zip(baseline_pct, current_pct)
        )

        if psi < self.PSI_WARNING:
            status = "stable"
        elif psi < self.PSI_CRITICAL:
            status = "warning"
        else:
            status = "drift_detected"

        result = {
            "psi": round(float(psi), 4),
            "status": status,
            "n_baseline": len(baseline_scores),
            "n_current": len(current_scores),
            "fraud_rate_baseline": round(sum(1 for s in baseline_scores if s >= 70) / len(baseline_scores), 4),
            "fraud_rate_current": round(sum(1 for s in current_scores if s >= 70) / len(current_scores), 4),
            "recommendation": "Model stable" if status == "stable" else "Monitor closely" if status == "warning" else "RETRAIN MODEL IMMEDIATELY"
        }

        await self.redis.set("drift:latest_psi", json.dumps(result), ex=3600)
        return result
