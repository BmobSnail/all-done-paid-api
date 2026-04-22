"""paid_api_keys / paid_api_key_audit_logs / paid_api_key_rollovers 模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infra.database import Base


class ApiKey(Base):
    """对外付费 API Key。"""

    __tablename__ = "paid_api_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    qps_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    concurrency_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    quota_daily: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rotated_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    audit_logs: Mapped[list["ApiKeyAuditLog"]] = relationship(
        back_populates="api_key", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_paid_api_keys_tenant_status", "tenant_id", "status"),
    )


class ApiKeyAuditLog(Base):
    """API Key 操作审计：发/吊/rotate/改 plan/补配额。"""

    __tablename__ = "paid_api_key_audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    api_key_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("paid_api_keys.id", ondelete="SET NULL"), nullable=True
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    api_key: Mapped["ApiKey | None"] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("ix_paid_api_key_audit_action_time", "action", "created_at"),
    )


class ApiKeyRollover(Base):
    """Key 轮换记录。"""

    __tablename__ = "paid_api_key_rollovers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    old_key_id: Mapped[str] = mapped_column(String(32), nullable=False)
    new_key_id: Mapped[str] = mapped_column(String(32), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
