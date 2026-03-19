"""Runtime experiment tracking for latency/throughput evaluation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from time import time
from typing import Any


@dataclass
class ExperimentTracker:
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=20000))
    event_times: deque[float] = field(default_factory=lambda: deque(maxlen=40000))
    model_outputs: deque[float] = field(default_factory=lambda: deque(maxlen=20000))
    started_at: float = field(default_factory=time)

    def record(self, latency_ms: float, risk_score: float | None = None) -> None:
        now = time()
        self.latencies_ms.append(float(latency_ms))
        self.event_times.append(now)
        if risk_score is not None:
            self.model_outputs.append(float(risk_score))

    def payload(self) -> dict[str, Any]:
        now = time()
        last_60 = [t for t in self.event_times if now - t <= 60]
        last_5 = [t for t in self.event_times if now - t <= 5]
        latencies = list(self.latencies_ms)

        if latencies:
            sorted_l = sorted(latencies)
            p95_idx = int(0.95 * (len(sorted_l) - 1))
            p99_idx = int(0.99 * (len(sorted_l) - 1))
            latency_summary = {
                "mean_ms": round(sum(latencies) / len(latencies), 3),
                "p95_ms": round(sorted_l[p95_idx], 3),
                "p99_ms": round(sorted_l[p99_idx], 3),
                "max_ms": round(max(latencies), 3),
                "samples": len(latencies),
            }
        else:
            latency_summary = {
                "mean_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "max_ms": 0.0,
                "samples": 0,
            }

        uptime = max(now - self.started_at, 1e-6)
        return {
            "latency": latency_summary,
            "throughput": {
                "tx_per_sec_last_5s": round(len(last_5) / 5.0, 3),
                "tx_per_sec_last_60s": round(len(last_60) / 60.0, 3),
                "tx_per_min_last_60s": len(last_60),
                "tx_per_sec_since_start": round(len(self.event_times) / uptime, 3),
            },
            "model_outputs": {
                "avg_risk_score": round(sum(self.model_outputs) / len(self.model_outputs), 4)
                if self.model_outputs
                else 0.0,
                "samples": len(self.model_outputs),
            },
        }


experiment_tracker = ExperimentTracker()
