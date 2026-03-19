from __future__ import annotations

"""
Kafka Producer — sends scored transactions to Kafka topics using aiokafka.
Topics: transactions.raw, transactions.scored, alerts.new
"""

import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer

from config import get_settings

logger = logging.getLogger(__name__)


class FraudKafkaProducer:
    def __init__(self):
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        settings = get_settings()
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            compression_type="gzip",
        )
        await self._producer.start()
        logger.info("Kafka producer started (%s)", settings.KAFKA_BOOTSTRAP)

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def send(self, topic: str, value: dict[str, Any], key: str | None = None) -> None:
        if not self._producer:
            logger.warning("Producer not started — dropping message to %s", topic)
            return
        await self._producer.send_and_wait(topic, value=value, key=key)

    async def send_raw_transaction(self, txn: dict) -> None:
        await self.send("transactions.raw", txn, key=txn.get("customer_id"))

    async def send_scored_transaction(self, scored: dict) -> None:
        await self.send("transactions.scored", scored, key=scored.get("customer_id"))

    async def send_alert(self, alert: dict) -> None:
        await self.send("alerts.new", alert, key=alert.get("customer_id"))
