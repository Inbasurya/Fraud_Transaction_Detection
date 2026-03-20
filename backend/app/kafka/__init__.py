"""Kafka producer — publishes raw transactions to transactions.raw topic."""

from __future__ import annotations

import json
import logging
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

_producer = None


def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    try:
        from confluent_kafka import Producer

        conf = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "fraud-producer",
            "acks": "all",
            "retries": 3,
            "linger.ms": 5,
            "batch.size": 16384,
        }
        _producer = Producer(conf)
        logger.info("Kafka producer connected to %s", settings.KAFKA_BOOTSTRAP_SERVERS)
        return _producer
    except Exception as exc:
        logger.warning("Kafka producer unavailable: %s", exc)
        return None


def _delivery_report(err, msg):
    if err is not None:
        logger.error("Kafka delivery failed: %s", err)


def publish_raw_transaction(transaction: dict[str, Any]) -> bool:
    """Publish a transaction to the raw topic. Returns True on success."""
    producer = _get_producer()
    if producer is None:
        return False
    try:
        key = str(transaction.get("transaction_id", "")).encode("utf-8")
        value = json.dumps(transaction, default=str).encode("utf-8")
        producer.produce(
            topic=settings.KAFKA_TOPIC_RAW,
            key=key,
            value=value,
            callback=_delivery_report,
        )
        producer.poll(0)
        return True
    except Exception as exc:
        logger.error("Failed to publish to Kafka: %s", exc)
        return False


def flush(timeout: float = 5.0) -> int:
    """Flush pending messages. Returns number remaining."""
    producer = _get_producer()
    if producer is None:
        return 0
    return producer.flush(timeout)
