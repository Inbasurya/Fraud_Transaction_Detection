"""Kafka consumer — reads transactions.raw, runs fraud pipeline, writes to transactions.scored."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from app.config import settings
from app.database import SessionLocal
from app.models.transaction_model import Transaction
from app.services import fraud_service

logger = logging.getLogger(__name__)


class FraudPipelineConsumer:
    """Reads from transactions.raw, runs detection, writes to transactions.scored."""

    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self.processed = 0
        self.failed = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="kafka-fraud-consumer")
        self._thread.start()
        logger.info("Kafka FraudPipelineConsumer started")

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def _run_loop(self) -> None:
        try:
            from confluent_kafka import Consumer, Producer, KafkaError
        except ImportError:
            logger.warning("confluent-kafka not installed — Kafka consumer disabled")
            return

        consumer_conf = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": settings.KAFKA_CONSUMER_GROUP,
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": 30000,
        }
        producer_conf = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "fraud-scored-producer",
        }

        consumer = Consumer(consumer_conf)
        producer = Producer(producer_conf)
        consumer.subscribe([settings.KAFKA_TOPIC_RAW])
        logger.info("Kafka consumer subscribed to %s", settings.KAFKA_TOPIC_RAW)

        try:
            while self._running:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Kafka consumer error: %s", msg.error())
                    continue

                try:
                    tx_data = json.loads(msg.value().decode("utf-8"))
                    result = self._process(tx_data)

                    scored_value = json.dumps(result, default=str).encode("utf-8")
                    producer.produce(
                        topic=settings.KAFKA_TOPIC_SCORED,
                        key=msg.key(),
                        value=scored_value,
                    )
                    producer.poll(0)
                    consumer.commit(asynchronous=False)
                    self.processed += 1
                except Exception as exc:
                    logger.error("Failed to process Kafka message: %s", exc)
                    self.failed += 1
                    consumer.commit(asynchronous=False)
        finally:
            consumer.close()
            producer.flush(10)

    def _process(self, tx_data: dict[str, Any]) -> dict[str, Any]:
        db = SessionLocal()
        try:
            tx_id = tx_data.get("id") or tx_data.get("transaction_db_id")
            if tx_id:
                tx = db.query(Transaction).filter(Transaction.id == int(tx_id)).first()
                if tx:
                    return await fraud_service.process_transaction(db, tx)

            return {
                "transaction_id": tx_data.get("transaction_id"),
                "risk_score": 0.0,
                "risk_category": "UNKNOWN",
                "error": "Transaction not found in DB",
            }
        finally:
            db.close()

    def stats(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "processed": self.processed,
            "failed": self.failed,
        }


class AlertConsumer:
    """Reads from transactions.scored and triggers alerts for high-risk transactions."""

    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self.alerts_triggered = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="kafka-alert-consumer")
        self._thread.start()
        logger.info("Kafka AlertConsumer started")

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def _run_loop(self) -> None:
        try:
            from confluent_kafka import Consumer, KafkaError
        except ImportError:
            logger.warning("confluent-kafka not installed — alert consumer disabled")
            return

        consumer_conf = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": f"{settings.KAFKA_CONSUMER_GROUP}-alerts",
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        }

        consumer = Consumer(consumer_conf)
        consumer.subscribe([settings.KAFKA_TOPIC_SCORED])
        logger.info("Kafka alert consumer subscribed to %s", settings.KAFKA_TOPIC_SCORED)

        try:
            while self._running:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    continue

                try:
                    scored = json.loads(msg.value().decode("utf-8"))
                    risk_score = float(scored.get("risk_score", 0))
                    risk_category = scored.get("risk_category", "SAFE")

                    if risk_category in ("FRAUD", "SUSPICIOUS") or risk_score >= 0.6:
                        self._trigger_alert(scored)
                        self.alerts_triggered += 1

                    consumer.commit(asynchronous=False)
                except Exception as exc:
                    logger.error("Alert consumer error: %s", exc)
                    consumer.commit(asynchronous=False)
        finally:
            consumer.close()

    def _trigger_alert(self, scored: dict[str, Any]) -> None:
        from app.websocket.manager import ws_manager

        db = SessionLocal()
        try:
            from app.services.alert_service_v2 import create_alert_from_scored
            create_alert_from_scored(db, scored)
        except Exception as exc:
            logger.error("Failed to create alert from scored tx: %s", exc)
        finally:
            db.close()

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast("alerts", {
                        "alert": {
                            "transaction_id": scored.get("transaction_id"),
                            "risk_score": scored.get("risk_score"),
                            "risk_category": scored.get("risk_category"),
                            "reasons": scored.get("reasons", []),
                        }
                    }),
                    loop,
                )
        except Exception:
            pass

    def stats(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "alerts_triggered": self.alerts_triggered,
        }


# Singletons
fraud_pipeline_consumer = FraudPipelineConsumer()
alert_consumer = AlertConsumer()
