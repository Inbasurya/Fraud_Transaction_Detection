"""Resilient Kafka consumer for the fraud-detection scoring pipeline.

Handles broker unavailability, unknown topics, and rebalance events
without crashing.  Designed to be driven as an ``asyncio.Task`` from
the FastAPI startup hook.
"""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Coroutine

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

_POLL_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kafka-poll")


class TransactionConsumer:
    """Consumes ``transactions.raw`` and forwards payloads to a scoring callback."""

    TOPIC = "transactions.raw"
    RETRY_INTERVAL_S = 5

    def __init__(
        self,
        scoring_callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self._consumer: Any | None = None
        self._running = False
        self._scoring_callback = scoring_callback
        self._subscribed = False

    # ── lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Create the underlying consumer and subscribe with retry."""
        try:
            from confluent_kafka import Consumer as CKConsumer
        except ImportError:
            logger.error("confluent_kafka_not_installed",
                          extra={"detail": "pip install confluent-kafka"})
            return

        conf: dict[str, Any] = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": "fraud-detector",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "session.timeout.ms": 30000,
            "max.poll.interval.ms": 300000,
        }

        try:
            self._consumer = CKConsumer(conf)
        except Exception as exc:
            logger.error("kafka_consumer_create_failed", extra={"error": str(exc)})
            return

        self._running = True
        await self._subscribe_with_retry()

    async def _subscribe_with_retry(self) -> None:
        """Subscribe to the topic, retrying every 5 s if broker / topic is unavailable."""
        while self._running and not self._subscribed:
            try:
                self._consumer.subscribe(
                    [self.TOPIC],
                    on_assign=self._on_assign,
                    on_revoke=self._on_revoke,
                )
                self._subscribed = True
                logger.info("kafka_subscribed", extra={"topic": self.TOPIC})
            except Exception as exc:
                logger.warning("kafka_subscribe_retry",
                                extra={"topic": self.TOPIC,
                                       "error": str(exc),
                                       "retry_in_s": self.RETRY_INTERVAL_S})
                await asyncio.sleep(self.RETRY_INTERVAL_S)

    # ── consume loop ──────────────────────────────────────────────

    async def consume_loop(self) -> None:
        """Async loop that polls in a thread executor to avoid blocking the event-loop."""
        if self._consumer is None:
            logger.warning("kafka_consume_loop_skipped",
                            extra={"reason": "consumer not initialised"})
            return

        from confluent_kafka import KafkaError

        loop = asyncio.get_running_loop()

        while self._running:
            try:
                msg = await loop.run_in_executor(_POLL_EXECUTOR, self._consumer.poll, 1.0)
            except Exception as exc:
                logger.error("kafka_poll_error", extra={"error": str(exc)})
                await asyncio.sleep(self.RETRY_INTERVAL_S)
                continue

            if msg is None:
                continue

            err = msg.error()
            if err is not None:
                if err.code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                    logger.warning("kafka_unknown_topic",
                                    extra={"topic": self.TOPIC,
                                           "detail": str(err),
                                           "action": "re-subscribing"})
                    self._subscribed = False
                    await asyncio.sleep(self.RETRY_INTERVAL_S)
                    await self._subscribe_with_retry()
                    continue
                if err.code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("kafka_consumer_error",
                              extra={"code": err.code(), "detail": str(err)})
                continue

            await self.process_message(msg)

            try:
                self._consumer.commit(asynchronous=False)
            except Exception as exc:
                logger.warning("kafka_commit_failed", extra={"error": str(exc)})

    # ── message processing ──────────────────────────────────────

    async def process_message(self, msg: Any) -> None:
        """Deserialise and forward to the scoring pipeline callback."""
        try:
            payload: dict[str, Any] = json.loads(msg.value().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error("kafka_message_decode_failed",
                          extra={"offset": msg.offset(),
                                 "partition": msg.partition(),
                                 "error": str(exc)})
            return

        logger.info("kafka_message_received",
                      extra={"offset": msg.offset(),
                             "partition": msg.partition(),
                             "transaction_id": payload.get("transaction_id")})

        if self._scoring_callback is not None:
            try:
                await self._scoring_callback(payload)
            except Exception as exc:
                logger.error("scoring_pipeline_error",
                              extra={"transaction_id": payload.get("transaction_id"),
                                     "error": str(exc)})

    # ── shutdown ────────────────────────────────────────────────

    async def stop(self) -> None:
        """Commit pending offsets and close the consumer cleanly."""
        self._running = False
        if self._consumer is not None:
            try:
                self._consumer.commit(asynchronous=False)
            except Exception:
                pass
            try:
                self._consumer.close()
            except Exception:
                pass
            self._consumer = None
            logger.info("kafka_consumer_stopped", extra={"topic": self.TOPIC})

    # ── rebalance callbacks ────────────────────────────────────

    @staticmethod
    def _on_assign(consumer: Any, partitions: list[Any]) -> None:
        logger.info("kafka_partitions_assigned",
                      extra={"partitions": [f"{p.topic}[{p.partition}]" for p in partitions]})

    @staticmethod
    def _on_revoke(consumer: Any, partitions: list[Any]) -> None:
        logger.info("kafka_partitions_revoked",
                      extra={"partitions": [f"{p.topic}[{p.partition}]" for p in partitions]})
