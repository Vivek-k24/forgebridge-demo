from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, LargeBinary, SmallInteger, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ProviderConnection(Base):
    __tablename__ = "provider_connections"
    __table_args__ = (
        CheckConstraint(
            "provider_kind IN ('internal_data', 'vehicle_data', 'ai', 'manufacturer')",
            name="ck_provider_connections_kind",
        ),
        CheckConstraint(
            "provider_key ~ '^[a-z0-9][a-z0-9_-]{1,95}$'",
            name="ck_provider_connections_key_format",
        ),
        CheckConstraint(
            "(credential_ciphertext IS NULL AND credential_nonce IS NULL "
            "AND credential_key_version IS NULL AND credential_fingerprint IS NULL "
            "AND credential_hint IS NULL) OR "
            "(credential_ciphertext IS NOT NULL AND credential_nonce IS NOT NULL "
            "AND credential_key_version IS NOT NULL AND credential_fingerprint IS NOT NULL "
            "AND credential_hint IS NOT NULL)",
            name="ck_provider_connections_encrypted_credential_complete",
        ),
        CheckConstraint(
            "credential_key_version IS NULL OR credential_key_version >= 1",
            name="ck_provider_connections_credential_key_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    provider_key: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
        unique=True,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(1024))
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    capabilities: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    secret_ref: Mapped[str | None] = mapped_column(String(255))
    credential_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    credential_nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    credential_key_version: Mapped[int | None] = mapped_column(SmallInteger)
    credential_fingerprint: Mapped[str | None] = mapped_column(String(64))
    credential_hint: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    updated_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OperatorAuditEvent(Base):
    __tablename__ = "operator_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('provider_created', 'provider_updated', 'provider_enabled', "
            "'provider_disabled', 'provider_credential_saved', 'provider_credential_removed')",
            name="ck_operator_audit_events_action",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, default="provider")
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    event_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
