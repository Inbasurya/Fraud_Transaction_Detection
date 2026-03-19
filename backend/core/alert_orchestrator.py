"""
Multi-channel alert orchestrator — mimics how HDFC/SBI actually alerts.

Channel priority based on risk score:
- Score 50-69: In-app notification only
- Score 70-84: In-app + SMS OTP
- Score 85-94: In-app + SMS + card step-down limit
- Score 95+:   In-app + SMS + card BLOCK + account freeze + SOC alert

All alerts logged to DB for audit trail (RBI compliance requirement).
"""
import asyncio
import json
from datetime import datetime
from enum import Enum

class AlertChannel(Enum):
    IN_APP = "in_app"
    SMS = "sms"
    EMAIL = "email"
    CARD_BLOCK = "card_block"
    ACCOUNT_FREEZE = "account_freeze"
    SOC_ESCALATION = "soc_escalation"
    KAFKA_EVENT = "kafka_event"

class AlertOrchestrator:
    def __init__(self, kafka_producer=None, ws_manager=None, db_session=None):
        self.kafka = kafka_producer
        self.ws = ws_manager
        self.db = db_session
        self.alert_log = []  # in-memory for now, write to DB in production

    async def process_transaction_alert(self, txn: dict, risk_score: float) -> dict:
        """
        Main entry point — decides channels and fires alerts simultaneously.
        Returns list of alerts sent for audit log.
        """
        alerts_sent = []
        channels = self._determine_channels(risk_score)
        tasks = []

        for channel in channels:
            if channel == AlertChannel.IN_APP:
                tasks.append(self._send_inapp_alert(txn, risk_score))
            elif channel == AlertChannel.SMS:
                tasks.append(self._send_sms_alert(txn, risk_score))
            elif channel == AlertChannel.CARD_BLOCK:
                tasks.append(self._block_card(txn))
            elif channel == AlertChannel.ACCOUNT_FREEZE:
                tasks.append(self._freeze_account(txn))
            elif channel == AlertChannel.SOC_ESCALATION:
                tasks.append(self._escalate_to_soc(txn, risk_score))
            elif channel == AlertChannel.KAFKA_EVENT:
                tasks.append(self._publish_kafka_event(txn, risk_score))

        # Fire all channels simultaneously (asyncio.gather)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for channel, result in zip(channels, results):
            alerts_sent.append({
                "channel": channel.value,
                "success": not isinstance(result, Exception),
                "timestamp": datetime.now().isoformat(),
                "txn_id": txn["id"]
            })

        # Log to audit trail
        await self._log_audit(txn, risk_score, alerts_sent)
        return {"alerts_sent": alerts_sent, "channels": [c.value for c in channels]}

    def _determine_channels(self, risk_score: float) -> list:
        if risk_score >= 95:
            return [
                AlertChannel.IN_APP,
                AlertChannel.SMS,
                AlertChannel.CARD_BLOCK,
                AlertChannel.ACCOUNT_FREEZE,
                AlertChannel.SOC_ESCALATION,
                AlertChannel.KAFKA_EVENT
            ]
        elif risk_score >= 85:
            return [
                AlertChannel.IN_APP,
                AlertChannel.SMS,
                AlertChannel.CARD_BLOCK,
                AlertChannel.KAFKA_EVENT
            ]
        elif risk_score >= 70:
            return [
                AlertChannel.IN_APP,
                AlertChannel.SMS,
                AlertChannel.KAFKA_EVENT
            ]
        else:  # 50-69
            return [AlertChannel.IN_APP, AlertChannel.KAFKA_EVENT]

    async def _send_sms_alert(self, txn: dict, risk_score: float) -> dict:
        """
        Simulate SMS via Twilio/AWS SNS/MSG91 (real implementation).
        In production: call MSG91 API or AWS SNS.
        For demo: log the message that WOULD be sent.
        """
        msg = self._build_sms_message(txn, risk_score)
        print(f"[SMS ALERT] To: {txn['customer_id']} | {msg}")
        # Production: await msg91_client.send(phone=customer.phone, message=msg)
        return {"status": "sent", "message": msg}

    def _build_sms_message(self, txn: dict, risk_score: float) -> str:
        amt = f"Rs.{txn['amount']:,.0f}"
        merchant = txn.get("merchant", "unknown merchant")
        if risk_score >= 85:
            return (
                f"FRAUD ALERT: Your card has been BLOCKED. "
                f"Suspicious transaction of {amt} at {merchant} detected. "
                f"If this was you, call 1800-XXX-XXXX. - FraudGuard"
            )
        else:
            otp = f"{__import__('random').randint(100000, 999999)}"
            return (
                f"FraudGuard OTP: {otp}. Transaction of {amt} at {merchant} "
                f"requires verification. Valid 5 min. Do NOT share. "
                f"If not you, call 1800-XXX-XXXX immediately."
            )

    async def _send_inapp_alert(self, txn: dict, risk_score: float) -> dict:
        """Push to SOC dashboard via WebSocket."""
        alert = {
            "type": "fraud_alert",
            "severity": "CRITICAL" if risk_score >= 85 else "HIGH" if risk_score >= 70 else "MEDIUM",
            "txn_id": txn["id"],
            "customer_id": txn["customer_id"],
            "amount": txn["amount"],
            "merchant": txn.get("merchant"),
            "risk_score": risk_score,
            "message": f"Risk score {risk_score} — {txn.get('scenario_description', 'Suspicious activity')}",
            "timestamp": datetime.now().isoformat(),
            "channels": []
        }
        if self.ws:
            await self.ws.broadcast(alert)
        return alert

    async def _block_card(self, txn: dict) -> dict:
        """
        In production: call card management API (Visa/Mastercard/RuPay).
        For demo: log the block action.
        """
        print(f"[CARD BLOCK] Customer: {txn['customer_id']} card blocked")
        return {"status": "blocked", "customer_id": txn["customer_id"]}

    async def _freeze_account(self, txn: dict) -> dict:
        print(f"[ACCOUNT FREEZE] Customer: {txn['customer_id']} account frozen")
        return {"status": "frozen", "customer_id": txn["customer_id"]}

    async def _escalate_to_soc(self, txn: dict, risk_score: float) -> dict:
        """Create a case in the SOC for analyst review."""
        case = {
            "case_id": f"CASE-{txn['id'][-6:]}",
            "priority": "P1",
            "txn_id": txn["id"],
            "customer_id": txn["customer_id"],
            "risk_score": risk_score,
            "assigned_to": "SOC-ANALYST-1",
            "status": "open",
            "created_at": datetime.now().isoformat()
        }
        print(f"[SOC ESCALATION] Case created: {case['case_id']}")
        return case

    async def _publish_kafka_event(self, txn: dict, risk_score: float) -> dict:
        """Publish to Kafka for downstream consumers (reporting, compliance)."""
        event = {
            "event_type": "fraud_detected" if risk_score >= 70 else "suspicious_activity",
            "txn_id": txn["id"],
            "risk_score": risk_score,
            "timestamp": datetime.now().isoformat()
        }
        if self.kafka:
            await self.kafka.send("fraud.alerts", json.dumps(event).encode())
        return event

    async def _log_audit(self, txn: dict, risk_score: float, alerts: list):
        """
        RBI mandates audit trail for all fraud alerts.
        Store in PostgreSQL audit_log table.
        """
        log_entry = {
            "txn_id": txn["id"],
            "customer_id": txn["customer_id"],
            "risk_score": risk_score,
            "alerts_sent": json.dumps(alerts),
            "timestamp": datetime.now().isoformat()
        }
        self.alert_log.append(log_entry)
        print(f"[AUDIT] Alert logged for {txn['id']}")
