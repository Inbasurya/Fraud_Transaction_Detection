"""Producer-consumer streaming engine with Redis Streams support."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.config import settings
from app.database import SessionLocal
from app.models.transaction_model import Transaction
from app.services import fraud_service
from app.analytics.experiment_tracker import experiment_tracker

try:
    import redis.asyncio as redis_asyncio
except Exception:  # pragma: no cover
    redis_asyncio = None


@dataclass
class StreamMessage:
    transaction_id: Any
    result_future: asyncio.Future


class RealtimeStreamingEngine:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[StreamMessage] = asyncio.Queue(maxsize=5000)
        self.consumer_task: asyncio.Task | None = None
        self._running = False
        self.processed = 0
        self.failed = 0

        self.mode = "memory"
        self.redis_client = None
        self.redis_stream = "fraud:transactions"
        self.redis_last_id = "$"
        self.pending: dict[str, asyncio.Future] = {}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True

        if redis_asyncio is not None:
            try:
                self.redis_client = redis_asyncio.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                )
                await self.redis_client.ping()
                self.mode = "redis"
            except Exception:
                self.redis_client = None
                self.mode = "memory"

        if self.mode == "redis":
            self.consumer_task = asyncio.create_task(self._consumer_loop_redis(), name="fraud-consumer-redis")
        else:
            self.consumer_task = asyncio.create_task(self._consumer_loop_memory(), name="fraud-consumer-memory")

    async def stop(self) -> None:
        self._running = False
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
            self.consumer_task = None

        if self.redis_client is not None:
            try:
                await self.redis_client.aclose()
            except Exception:
                pass
            self.redis_client = None

    async def submit(self, transaction_id: Any) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()

        if self.mode == "redis" and self.redis_client is not None:
            try:
                msg_id = await self.redis_client.xadd(
                    self.redis_stream,
                    {"transaction_id": str(transaction_id)},
                    maxlen=50000,
                    approximate=True,
                )
                self.pending[str(msg_id)] = fut
                return await fut
            except Exception:
                self.mode = "memory"

        await self.queue.put(StreamMessage(transaction_id=transaction_id, result_future=fut))
        return await fut

    async def _process_transaction(self, transaction_id: Any) -> dict[str, Any]:
        db = SessionLocal()
        try:
            started = perf_counter()
            tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
            if not tx:
                raise ValueError(f"Transaction {transaction_id} not found")
            payload = await fraud_service.process_transaction(db, tx)
            elapsed_ms = (perf_counter() - started) * 1000.0
            experiment_tracker.record(elapsed_ms, float(payload.get("risk_score") or 0.0))
            self.processed += 1
            return payload
        except Exception:
            self.failed += 1
            raise
        finally:
            db.close()

    async def _consumer_loop_memory(self) -> None:
        while self._running:
            msg = await self.queue.get()
            try:
                payload = await self._process_transaction(msg.transaction_id)
                if not msg.result_future.done():
                    msg.result_future.set_result(payload)
            except Exception as exc:
                if not msg.result_future.done():
                    msg.result_future.set_exception(exc)
            finally:
                self.queue.task_done()

    async def _consumer_loop_redis(self) -> None:
        while self._running and self.redis_client is not None:
            try:
                batches = await self.redis_client.xread(
                    {self.redis_stream: self.redis_last_id},
                    block=1000,
                    count=32,
                )
                if not batches:
                    continue
                for _stream, messages in batches:
                    for msg_id, fields in messages:
                        self.redis_last_id = msg_id
                        tx_id = fields.get("transaction_id", "")
                        fut = self.pending.pop(str(msg_id), None)
                        try:
                            payload = await self._process_transaction(tx_id)
                            if fut is not None and not fut.done():
                                fut.set_result(payload)
                        except Exception as exc:
                            if fut is not None and not fut.done():
                                fut.set_exception(exc)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(0.25)

    def stats(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "queued": self.queue.qsize(),
            "redis_pending": len(self.pending),
            "processed": self.processed,
            "failed": self.failed,
            "consumer_running": bool(self.consumer_task and not self.consumer_task.done()),
        }


streaming_engine = RealtimeStreamingEngine()
