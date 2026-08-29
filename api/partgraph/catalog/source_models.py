from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .models import CatalogVerifiedEvidence


class CatalogSource(Base):
    """Governance metadata for a source; raw ingestion still lands in catalog_staging."""

    __tablename__ = "catalog_sources"
    __table_args__ = (
        CheckConstraint(
            "source_class IN ('government', 'oem_service', 'licensed_oem_derived', "
            "'oem_parts', 'industry_standard', 'retailer', 'community')",
            name="ck_catalog_sources_class",
        ),
        CheckConstraint(
            "license_status IN ('unreviewed', 'approved', 'prohibited')",
            name="ck_catalog_sources_license_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_key: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_class: Mapped[str] = mapped_column(String(32), nullable=False)
    license_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unreviewed"
    )
    automation_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    terms_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MechanicalClaim(Base):
    """Normalized claim supported by immutable verified evidence.

    A claim becomes canonical repair truth only when attached to the exact
    repair-definition structure that consumes it.
    """

    __tablename__ = "mechanical_claims"
    __table_args__ = (
        CheckConstraint(
            "claim_domain IN ('vehicle_identity', 'safety_campaign', "
            "'repair_requirement', 'repair_procedure', 'part_fitment')",
            name="ck_mechanical_claims_domain",
        ),
        CheckConstraint(
            "claim_risk IN ('normal', 'safety_critical')",
            name="ck_mechanical_claims_risk",
        ),
        CheckConstraint(
            "promotion_state IN ('staged', 'needs_review', 'verified', 'rejected', "
            "'conflict', 'superseded')",
            name="ck_mechanical_claims_promotion_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("catalog_sources.id", ondelete="RESTRICT"), nullable=False
    )
    verified_evidence_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(CatalogVerifiedEvidence.id, ondelete="RESTRICT"),
        nullable=False,
    )
    vehicle_configuration_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
    )
    claim_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    claim_risk: Mapped[str] = mapped_column(String(24), nullable=False, default="normal")
    normalized_key: Mapped[str] = mapped_column(String(160), nullable=False)
    repair_key: Mapped[str | None] = mapped_column(String(120))
    claim_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    explicit_claim: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exact_applicability: Mapped[bool] = mapped_column(Boolean, nullable=False)
    promotion_state: Mapped[str] = mapped_column(String(24), nullable=False)
    conflict_key: Mapped[str | None] = mapped_column(String(128), index=True)
    superseded_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("mechanical_claims.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
