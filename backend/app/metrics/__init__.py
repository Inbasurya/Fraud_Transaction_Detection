"""Prometheus metrics endpoint and middleware.

Metrics:
- fraud_decisions_total (counter, by risk_level)
- fraud_detection_latency_seconds (histogram)
- model_prediction_latency_seconds (histogram)
- kafka_consumer_lag (gauge)
- active_websocket_connections (gauge)
"""

from __future__ import annotations

import time
import logging
from typing import Any

from fastapi import APIRouter, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Use prometheus_client if available, otherwise fallback to simple counters
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    FRAUD_DECISIONS = Counter(
        "fraud_decisions_total",
        "Total fraud detection decisions",
        ["risk_level"],
    )
    FRAUD_LATENCY = Histogram(
        "fraud_detection_latency_seconds",
        "End-to-end fraud detection latency",
        buckets=[0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.5, 5.0],
    )
    MODEL_LATENCY = Histogram(
        "model_prediction_latency_seconds",
        "ML model prediction latency",
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    )
    KAFKA_LAG = Gauge(
        "kafka_consumer_lag",
        "Kafka consumer lag",
        ["consumer_group"],
    )
    WS_CONNECTIONS = Gauge(
        "active_websocket_connections",
        "Active WebSocket connections",
        ["room"],
    )
    HTTP_REQUESTS = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    HTTP_LATENCY = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0],
    )
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False
    logger.info("prometheus_client not installed — metrics endpoint returns JSON fallback")


# ── Simple fallback counters ──
_fallback_counters: dict[str, int] = {}
_fallback_histograms: dict[str, list[float]] = {}


def record_fraud_decision(risk_level: str) -> None:
    """Record a fraud detection decision."""
    if _HAS_PROMETHEUS:
        FRAUD_DECISIONS.labels(risk_level=risk_level).inc()
    else:
        key = f"fraud_decisions_{risk_level}"
        _fallback_counters[key] = _fallback_counters.get(key, 0) + 1


def record_fraud_latency(seconds: float) -> None:
    """Record end-to-end fraud detection latency."""
    if _HAS_PROMETHEUS:
        FRAUD_LATENCY.observe(seconds)
    else:
        _fallback_histograms.setdefault("fraud_latency", []).append(seconds)


def record_model_latency(seconds: float) -> None:
    """Record ML model prediction latency."""
    if _HAS_PROMETHEUS:
        MODEL_LATENCY.observe(seconds)
    else:
        _fallback_histograms.setdefault("model_latency", []).append(seconds)


def update_kafka_lag(consumer_group: str, lag: int) -> None:
    if _HAS_PROMETHEUS:
        KAFKA_LAG.labels(consumer_group=consumer_group).set(lag)


def update_ws_connections(room: str, count: int) -> None:
    if _HAS_PROMETHEUS:
        WS_CONNECTIONS.labels(room=room).set(count)


# ── Metrics route ──

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def metrics_endpoint():
    """Prometheus-compatible metrics endpoint."""
    if _HAS_PROMETHEUS:
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # Fallback JSON
    import json
    data = {
        "counters": _fallback_counters,
        "histograms": {
            k: {
                "count": len(v),
                "mean": sum(v) / len(v) if v else 0,
                "p95": sorted(v)[int(len(v) * 0.95)] if v else 0,
            }
            for k, v in _fallback_histograms.items()
        },
    }
    return Response(content=json.dumps(data), media_type="application/json")


# ── Middleware for HTTP metrics ──

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        if _HAS_PROMETHEUS:
            path = request.url.path
            # Normalize path to avoid high cardinality
            if any(path.startswith(p) for p in ["/api/", "/ws/", "/metrics"]):
                parts = path.split("/")
                normalized = "/".join(parts[:4]) if len(parts) > 4 else path
                HTTP_REQUESTS.labels(
                    method=request.method,
                    endpoint=normalized,
                    status=str(response.status_code),
                ).inc()
                HTTP_LATENCY.labels(
                    method=request.method,
                    endpoint=normalized,
                ).observe(elapsed)

        return response
