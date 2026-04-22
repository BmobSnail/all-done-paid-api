"""init paid_* tables

Revision ID: 0001_init_paid_tables
Revises:
Create Date: 2026-04-22 20:30:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init_paid_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------- paid_api_keys ----------
    op.create_table(
        "paid_api_keys",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("key_id", sa.String(32), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("last4", sa.String(4), nullable=False),
        sa.Column("secret_hash", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False, server_default="free"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("qps_limit", sa.Integer, nullable=False, server_default="10"),
        sa.Column("concurrency_limit", sa.Integer, nullable=False, server_default="20"),
        sa.Column("quota_daily", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_from", sa.String(32), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key_id", name="uq_paid_api_keys_key_id"),
    )
    op.create_index("ix_paid_api_keys_key_id", "paid_api_keys", ["key_id"])
    op.create_index("ix_paid_api_keys_tenant_id", "paid_api_keys", ["tenant_id"])
    op.create_index(
        "ix_paid_api_keys_tenant_status", "paid_api_keys", ["tenant_id", "status"]
    )

    # ---------- paid_api_key_audit_logs ----------
    op.create_table(
        "paid_api_key_audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "api_key_id",
            sa.BigInteger,
            sa.ForeignKey("paid_api_keys.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("target", sa.String(128), nullable=True),
        sa.Column("before_json", sa.Text, nullable=True),
        sa.Column("after_json", sa.Text, nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_paid_api_key_audit_action_time",
        "paid_api_key_audit_logs",
        ["action", "created_at"],
    )

    # ---------- paid_api_key_rollovers ----------
    op.create_table(
        "paid_api_key_rollovers",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("old_key_id", sa.String(32), nullable=False),
        sa.Column("new_key_id", sa.String(32), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_paid_api_key_rollovers_tenant_id", "paid_api_key_rollovers", ["tenant_id"])

    # ---------- paid_billing_events ----------
    op.create_table(
        "paid_billing_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("api_key_id", sa.BigInteger, nullable=True),
        sa.Column("endpoint", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("token_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("token_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("raw_meta_json", sa.Text, nullable=True),
        sa.Column("error_code", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("request_id", name="uq_paid_billing_request_id"),
    )
    op.create_index("ix_paid_billing_request_id", "paid_billing_events", ["request_id"])
    op.create_index("ix_paid_billing_tenant_id", "paid_billing_events", ["tenant_id"])
    op.create_index("ix_paid_billing_api_key_id", "paid_billing_events", ["api_key_id"])
    op.create_index(
        "ix_paid_billing_idempotency_key", "paid_billing_events", ["idempotency_key"]
    )
    op.create_index(
        "ix_paid_billing_tenant_endpoint_time",
        "paid_billing_events",
        ["tenant_id", "endpoint", "created_at"],
    )
    op.create_index(
        "ix_paid_billing_status_time", "paid_billing_events", ["status", "created_at"]
    )

    # ---------- paid_usage_hourly ----------
    op.create_table(
        "paid_usage_hourly",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("endpoint", sa.String(128), nullable=False),
        sa.Column("hour_bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("req_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("token_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("token_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "endpoint", "hour_bucket", name="uq_paid_usage_bucket"),
    )
    op.create_index(
        "ix_paid_usage_tenant_hour", "paid_usage_hourly", ["tenant_id", "hour_bucket"]
    )

    # ---------- paid_idempotency_keys ----------
    op.create_table(
        "paid_idempotency_keys",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(128), nullable=False),
        sa.Column("response_hash", sa.String(128), nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "key", name="uq_paid_idempotency_tenant_key"),
    )
    op.create_index("ix_paid_idempotency_expires", "paid_idempotency_keys", ["expires_at"])


def downgrade() -> None:
    op.drop_table("paid_idempotency_keys")
    op.drop_table("paid_usage_hourly")
    op.drop_table("paid_billing_events")
    op.drop_table("paid_api_key_rollovers")
    op.drop_table("paid_api_key_audit_logs")
    op.drop_table("paid_api_keys")
