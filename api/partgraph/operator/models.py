from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Uuid, func
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
