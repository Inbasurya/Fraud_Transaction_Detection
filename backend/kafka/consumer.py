from __future__ import annotations

"""
Kafka Consumer — reads from transactions.raw, runs the full scoring pipeline,
publishes results to transactions.scored and alerts.new.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaConsumer

from config import get_settings
from core.feature_store import FeatureStore
from core.rule_engine import RuleEngine
from core.ml_engine import MLEngine
from core.behavioral_engine import BehavioralEngine
from core.graph_engine import GraphEngine
from core.scoring import ScoringEngine
from kafka import FraudKafkaProducer
from core.fraud_memory import fraud_memory
from core.sms_service import send_fraud_alert_sms, send_preventive_alert_sms

logger = logging.getLogger(__name__)


class FraudKafkaConsumer:
    """
    Consumes raw transactions, runs rule+ML+behavioral+graph scoring,
    and publishes scored transactions and alerts.
    """

    def __init__(
        self,
        feature_store: FeatureStore,
        rule_engine: RuleEngine,
        ml_engine: MLEngine,
        behavioral_engine: BehavioralEngine,
        graph_engine: GraphEngine,
        risk_scorer: ScoringEngine,
        producer: FraudKafkaProducer,
        on_scored_callback=None,
    ):
        self.feature_store = feature_store
        self.rule_engine = rule_engine
        self.ml_engine = ml_engine
        self.behavioral_engine = behavioral_engine
        self.graph_engine = graph_engine
        self.risk_scorer = risk_scorer
        self.producer = producer
        self.on_scored_callback = on_scored_callback
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        settings = get_settings()
        self._consumer = AIOKafkaConsumer(
            "transactions.raw",
            bootstrap_servers=settings.KAFKA_BOOTSTRAP,
            group_id="fraud-scoring-group",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self._consumer.start()
        logger.info("Kafka consumer started on transactions.raw")

    async def stop(self) -> None:
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped")

    async def consume_loop(self) -> None:
        """Main processing loop — runs until cancelled."""
        if not self._consumer:
            await self.start()

        async for msg in self._consumer:
            try:
                txn = msg.value
                scored = await self._process_transaction(txn)

                # Publish scored transaction
                await self.producer.send_scored_transaction(scored)

                # If high/critical → publish alert
                if scored.get("risk_level") in ("high", "critical"):
                    alert = self._build_alert(scored)
                    await self.producer.send_alert(alert)

                # Callback for WebSocket broadcast
                if self.on_scored_callback:
                    await self.on_scored_callback(scored)

            except Exception as exc:
                logger.error("Error processing message: %s", exc, exc_info=True)

    async def _process_transaction(self, txn: dict) -> dict:
        """Run the full scoring pipeline on a single transaction."""
        t0 = time.monotonic()
        logger.info(
            "[INGEST] txn=%s customer=%s amount=%s merchant=%s",
            txn.get("id"),
            txn.get("customer_id"),
            txn.get("amount"),
            txn.get("merchant", txn.get("merchant_category")),
        )

        # 1) Get features (based on prior history only)
        features = await self.feature_store.get_features(txn)

        # 2) Rule engine
        rule_score, triggered_rules = self.rule_engine.evaluate(txn, features)

        # 3) ML engine
        ml_result = await self.ml_engine.predict(txn, features)

        # 4) Behavioral engine
        behavioral_result = await self.behavioral_engine.score(txn, features)
        await self.behavioral_engine.update_profile(txn)

        # 5) Graph engine
        self.graph_engine.add_transaction(txn)
        graph_result = self.graph_engine.score(txn)


        # 6) Combine scores
        risk_result = self.risk_scorer.score(
            rule_score=rule_score,
            ml_score=ml_result["ml_score"],
            behavioral_score=behavioral_result["behavioral_score"],
            graph_score=graph_result["graph_score"],
            shap_values=ml_result.get("shap_values"),
            triggered_rules=triggered_rules
        )
        logger.info(
            "[RISK] txn=%s rule=%.3f ml=%.3f behavioral=%.3f graph=%.3f final=%.1f decision=%s top_features=%s",
            txn.get("id"),
            rule_score,
            ml_result["ml_score"],
            behavioral_result["behavioral_score"],
            graph_result["graph_score"],
            risk_result["risk_score"],
            risk_result.get("decision"),
            risk_result.get("top_features", [])[:3],
        )

        # 7) Persist transaction into feature windows after scoring
        await self.feature_store.record_transaction(txn)

        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        decision = risk_result.get("decision", "Approve")

        scored = {
            **txn,
            "risk_score": risk_result["risk_score"],
            "decision": decision,
            "risk_level": risk_result["risk_level"],
            "score_breakdown": risk_result["score_breakdown"],
            "triggered_rules": triggered_rules,
            "patterns_matched": risk_result.get("patterns_matched", []),
            "explanation": risk_result.get("explanation", "Normal"),
            "ml_score": ml_result["ml_score"],
            "shap_values": ml_result.get("shap_values"),
            "behavioral_score": behavioral_result["behavioral_score"],
            "graph_score": graph_result["graph_score"],
            "processing_latency_ms": latency_ms,
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }

        # 8) Alerting Logic (Async SMS)
        if decision == "Block":
            
            # Record in memory for repeated check
            await fraud_memory.record_blocked_transaction(scored)
            
            # A) High-risk SMS (Risk > 90)
            if risk_result["risk_score"] > 90:
                asyncio.create_task(
                    send_fraud_alert_sms(
                        txn.get("phone_number", ""),
                        float(scored.get("amount", 0)),
                        str(scored.get("merchant", "")),
                    )
                )
                logger.info(f"SMS Alert Task created for high-risk block: {txn.get('id')}")
                
            # B) Repeated Attempt SMS (3 in 60m)
            if await fraud_memory.should_send_preventive_sms(txn.get('customer_id')):
                asyncio.create_task(send_preventive_alert_sms(txn.get("phone_number", "")))
                await fraud_memory.mark_preventive_alert_sent(txn.get('customer_id'))
                logger.info(f"Preventive SMS Task created for {txn.get('customer_id')}")

        return scored

    @staticmethod
    def _build_alert(scored: dict) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "transaction_id": scored.get("id", ""),
            "customer_id": scored.get("customer_id", ""),
            "severity": scored.get("risk_level", "medium"),
            "risk_score": scored.get("risk_score", 0),
            "triggered_rules": scored.get("triggered_rules", []),
            "status": "new",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
