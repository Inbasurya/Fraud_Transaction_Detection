"""
Async background writer — saves every scored transaction to PostgreSQL.
Uses asyncpg connection pool for high throughput.
Batches writes every 100ms to avoid overwhelming Postgres.
"""
import asyncio
import json
from datetime import datetime
from typing import List
from database import async_session
from models.transaction import Transaction as TxnModel

class TransactionWriter:
    def __init__(self):
        self.buffer: List[dict] = []
        self.flush_interval = 0.1  # 100ms batching
        self._running = False

    async def add(self, txn: dict):
        """Add transaction to write buffer."""
        self.buffer.append(txn)

    async def start(self):
        """Background loop — flushes buffer to Postgres."""
        self._running = True
        while self._running:
            if self.buffer:
                batch = self.buffer.copy()
                self.buffer.clear()
                await self._flush(batch)
            await asyncio.sleep(self.flush_interval)

    async def _flush(self, batch: List[dict]):
        try:
            async with async_session() as session:
                for txn in batch:
                    # Map WebSocket emit format to DB model format
                    db_txn = TxnModel(
                        customer_id=txn.get("customer_id", "unknown"),
                        amount=float(txn.get("amount", 0.0)),
                        merchant_id=txn.get("merchant", "unknown"),
                        merchant_category=txn.get("merchant_category", "unknown"),
                        lat=txn.get("lat", None),
                        lng=txn.get("lng", None),
                        device_fingerprint=txn.get("device", "unknown"),
                        ip_address=txn.get("ip_address", "0.0.0.0"),
                        risk_score=float(txn.get("risk_score", 0.0)),
                        risk_level=txn.get("risk_level", "safe"),
                        action_taken=txn.get("action", "approve"),
                        score_breakdown=txn.get("score_breakdown", {}),
                        triggered_rules=txn.get("triggered_rules", []),
                        shap_values=txn.get("shap_values", {}),
                        is_fraud=True if txn.get("risk_level") == "fraudulent" else False,
                    )
                    session.add(db_txn)
                await session.commit()
        except Exception as e:
            print(f"DB write error: {e}")

writer = TransactionWriter()
