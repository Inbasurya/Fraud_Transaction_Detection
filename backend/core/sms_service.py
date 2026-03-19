import os
import asyncio
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

# ── Load .env at import time ──
def _load_env():
    env_paths = [Path(__file__).parent.parent / ".env", Path(".env"), Path("backend/.env")]
    for path in env_paths:
        if path.exists():
            load_dotenv(path, override=True)
            logger.info("Loaded env from %s", path)
            break

_load_env()


class SMSAlertService:
    """Production Twilio SMS service for fraud alerts."""

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER")
        self.to_number = os.getenv("ALERT_PHONE_NUMBER")
        self.client = None
        self.enabled = all([self.account_sid, self.auth_token,
                            self.from_number, self.to_number])
        if self.enabled:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("SMS service initialized (from=%s, to=%s)",
                            self.from_number, self.to_number)
            except Exception as exc:
                logger.error("Twilio client init failed: %s", exc)
                self.enabled = False
        else:
            missing = [v for v in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
                                   "TWILIO_FROM_NUMBER", "ALERT_PHONE_NUMBER")
                       if not os.getenv(v)]
            logger.warning("SMS service DISABLED — missing env vars: %s", missing)

    # ── public helpers ──────────────────────────────────────

    async def send_fraud_alert(self, txn_data: dict) -> bool:
        """Send SMS for a blocked/high-risk transaction."""
        if not self.enabled:
            logger.warning("SMS not sent — service disabled")
            return False

        score = txn_data.get("risk_score", 0)
        txn_id = str(txn_data.get("id", txn_data.get("transaction_id", "unknown")))[:8]
        customer = txn_data.get("customer_id", "unknown")
        amount = float(txn_data.get("amount", 0))
        merchant = txn_data.get("merchant", "unknown")
        city = txn_data.get("city", "unknown")
        reason = (txn_data.get("fraud_scenario")
                  or txn_data.get("scenario_description")
                  or "Fraud detected")

        if amount >= 100_000:
            amount_str = f"Rs.{amount/100_000:.1f}L"
        elif amount >= 1_000:
            amount_str = f"Rs.{amount/1_000:.1f}K"
        else:
            amount_str = f"Rs.{amount:.0f}"

        severity = "CRITICAL FRAUD" if score >= 90 else "FRAUD BLOCKED"

        message = (
            f"{severity} ALERT - FraudGuard\n"
            f"Score: {score}/100\n"
            f"TXN: {txn_id}\n"
            f"Customer: {customer}\n"
            f"Amount: {amount_str}\n"
            f"Merchant: {merchant}\n"
            f"City: {city}\n"
            f"Reason: {reason}\n"
            f"Action: BLOCKED"
        )
        return await self._send(message, txn_id, score)

    async def send_prevention_warning(self, phone: Optional[str] = None) -> bool:
        """Send prevention warning for repeat suspicious activity."""
        if not self.enabled:
            return False
        msg = (
            "SECURITY ALERT: Multiple suspicious attempts were blocked on your account. "
            "Transaction limits have been reduced temporarily. "
            "If these weren't you, call 1800-FRAUDGUARD immediately."
        )
        return await self._send(msg, "PREVENTION", 0, target_override=phone)

    async def send_test_sms(self) -> bool:
        """Send a test SMS to verify configuration."""
        test_data = {
            "id": "TEST-001",
            "customer_id": "CUS-TEST",
            "amount": 125000,
            "merchant": "Crypto Exchange INR",
            "city": "Mumbai",
            "risk_score": 93,
            "fraud_scenario": "Test alert - system working",
        }
        return await self.send_fraud_alert(test_data)

    # ── internal ────────────────────────────────────────────

    async def _send(self, body: str, txn_id: str, score: float,
                    target_override: Optional[str] = None) -> bool:
        target = target_override or self.to_number
        try:
            msg = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.messages.create,
                    body=body,
                    from_=self.from_number,
                    to=target,
                ),
                timeout=10.0,  # 10s hard cap — prevents event loop stalls
            )
            logger.info("SMS sent SID=%s | TXN=%s | score=%s | to=%s",
                        msg.sid, txn_id, score, target)
            return True
        except asyncio.TimeoutError:
            logger.error("SMS timed out after 10s for TXN=%s (Twilio API unresponsive)", txn_id)
            return False
        except TwilioRestException as exc:
            logger.error("Twilio API error %s: %s", exc.code, exc.msg)
            if exc.code == 21211:
                logger.error("Invalid 'to' phone number format")
            elif exc.code == 21214:
                logger.error("'To' number not verified (trial account)")
            elif exc.code == 20003:
                logger.error("Authentication failed — check SID/token")
            return False
        except Exception as exc:
            logger.error("SMS send failed: %s", exc)
            return False


# ── Singleton ───────────────────────────────────────────────
sms_service = SMSAlertService()


# ── Backward-compatible module-level functions ──────────────
async def send_blocked_transaction_sms(phone_number: str, txn_details: dict, risk_score: float) -> bool:
    """Drop-in replacement keeping the old call signature used in ws.py."""
    txn_details["risk_score"] = risk_score
    return await sms_service.send_fraud_alert(txn_details)


async def send_prevention_warning_sms(phone_number: str) -> bool:
    return await sms_service.send_prevention_warning(phone_number)


async def send_fraud_alert_sms(phone_number: str, amount: float = 0, merchant: str = "") -> bool:
    return await sms_service.send_fraud_alert({
        "amount": amount, "merchant": merchant, "risk_score": 85,
    })


async def send_preventive_alert_sms(phone_number: str) -> bool:
    return await sms_service.send_prevention_warning(phone_number)
