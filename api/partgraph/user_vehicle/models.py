from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, LargeBinary, SmallInteger, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class UserVehicle(Base):
    __tablename__ = "user_vehicles"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_configuration_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    nickname: Mapped[str | None] = mapped_column(String(80))
    identity_source: Mapped[str] = mapped_column(String(16), nullable=False)
    identity_resolution: Mapped[str] = mapped_column(String(32), nullable=False)
    identity_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    vin_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    vin_nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    vin_key_version: Mapped[int | None] = mapped_column(SmallInteger)
    vin_fingerprint: Mapped[str | None] = mapped_column(String(64))
    vin_last6: Mapped[str | None] = mapped_column(String(6))
    decoder_provider: Mapped[str | None] = mapped_column(String(32))
    decoder_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class VinDecodeCache(Base):
    __tablename__ = "vin_decode_cache"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vin_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    identity_resolution: Mapped[str] = mapped_column(String(32), nullable=False)
    identity_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    canonical_match_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
