"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-13
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # transactions table
    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("merchant_id", sa.String(60)),
        sa.Column("merchant_category", sa.String(40)),
        sa.Column("lat", sa.Numeric(9, 6)),
        sa.Column("lng", sa.Numeric(9, 6)),
        sa.Column("device_fingerprint", sa.String(100)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("risk_score", sa.Numeric(5, 2)),
        sa.Column("risk_level", sa.String(20)),
        sa.Column("action_taken", sa.String(30)),
        sa.Column("score_breakdown", JSONB),
        sa.Column("triggered_rules", JSONB),
        sa.Column("shap_values", JSONB),
        sa.Column("is_fraud", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_txn_customer_id", "transactions", ["customer_id"])
    op.create_index("ix_txn_customer_created", "transactions", ["customer_id", "created_at"])
    op.create_index("ix_txn_risk_level", "transactions", ["risk_level"])


    # customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("segment", sa.String(30)),
        sa.Column("home_city", sa.String(50)),
        sa.Column("avg_txn_amount", sa.Numeric(12, 2)),
        sa.Column("monthly_txn_count", sa.Integer),
        sa.Column("risk_tier", sa.String(10), server_default="low"),
        sa.Column("total_transactions", sa.Integer, server_default="0"),
        sa.Column("fraud_count", sa.Integer, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("registered_devices", JSONB),
        sa.Column("behavioral_profile", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


    # alerts table
    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("transaction_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", sa.String(40), nullable=False),
        sa.Column("alert_type", sa.String(50)),
        sa.Column("severity", sa.String(20)),
        sa.Column("title", sa.String(200)),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("assigned_to", sa.String(100)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolution", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


    # audit log
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("transaction_id", UUID(as_uuid=True), nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 2)),
        sa.Column("action_taken", sa.String(30)),
        sa.Column("model_version", sa.String(50)),
        sa.Column("score_breakdown", JSONB),
        sa.Column("triggered_rules", JSONB),
        sa.Column("shap_values", JSONB),
        sa.Column("analyst_override", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("alerts")
    op.drop_table("customers")
    op.drop_table("transactions")