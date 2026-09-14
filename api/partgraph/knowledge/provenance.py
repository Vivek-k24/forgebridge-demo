from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

CANONICAL_DOMAINS = (
    "vehicle_identity",
    "structure",
    "part_identity",
    "fitment",
    "interchange",
    "physical_relationship",
    "hardware",
    "requirement",
    "material",
    "specification",
    "repair",
    "procedure",
    "downstream",
    "diagnostic",
    "electrical",
    "capability",
)
_CANONICAL_DOMAIN_SQL = ", ".join(f"'{item}'" for item in CANONICAL_DOMAINS)
_SOURCE_CLASS_SQL = (
    "'government', 'oem_service', 'licensed_oem_derived', 'oem_parts', "
    "'industry_standard', 'retailer', 'community'"
)


class SourceAuthorityPolicy(Base):
    """Policy describing whether a source class is acceptable for a canonical domain/risk."""

    __tablename__ = "source_authority_policies"
    __table_args__ = (
        CheckConstraint(
            f"canonical_domain IN ({_CANONICAL_DOMAIN_SQL})",
            name="ck_source_authority_policies_domain",
        ),
        CheckConstraint(
            f"source_class IN ({_SOURCE_CLASS_SQL})",
            name="ck_source_authority_policies_source_class",
        ),
        CheckConstraint(
            "risk_class IN ('normal', 'safety_critical')",
            name="ck_source_authority_policies_risk",
        ),
        CheckConstraint(
            "authority_state IN ('accepted', 'conditional', 'rejected')",
            name="ck_source_authority_policies_state",
        ),
        CheckConstraint(
            "minimum_evidence_count >= 1",
            name="ck_source_authority_policies_evidence_count",
        ),
        UniqueConstraint(
            "canonical_domain",
            "source_class",
            "risk_class",
            name="uq_source_authority_policies_scope",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    policy_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    canonical_domain: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_class: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(24), nullable=False)
    authority_state: Mapped[str] = mapped_column(String(16), nullable=False)
    requires_exact_applicability: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    minimum_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rationale: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CanonicalRecordVersion(Base):
    """Publication/version envelope for a canonical knowledge record.

    The domain table remains the mechanical source of truth. This record gives
    that canonical row an auditable publication version without making source
    evidence or an LLM authoritative over runtime repair behavior.
    """

    __tablename__ = "canonical_record_versions"
    __table_args__ = (
        CheckConstraint(
            f"canonical_domain IN ({_CANONICAL_DOMAIN_SQL})",
            name="ck_canonical_record_versions_domain",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_canonical_record_versions_version",
        ),
        CheckConstraint(
            "publication_state IN ('verified', 'superseded', 'withdrawn')",
            name="ck_canonical_record_versions_state",
        ),
        UniqueConstraint(
            "canonical_domain",
            "record_type",
            "record_id",
            "version",
            name="uq_canonical_record_versions_identity",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_canonical_record_versions_idempotency_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    canonical_domain: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    record_type: Mapped[str] = mapped_column(String(96), nullable=False)
    record_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    publication_state: Mapped[str] = mapped_column(String(16), nullable=False)
    supersedes_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("canonical_record_versions.id", ondelete="SET NULL"),
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_sha256: Mapped[str | None] = mapped_column(String(64))
    published_by: Mapped[str] = mapped_column(String(128), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CanonicalRecordEvidence(Base):
    """Immutable evidence/claim link supporting one canonical publication version."""

    __tablename__ = "canonical_record_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_role IN ('supports', 'excludes', 'conflicts')",
            name="ck_canonical_record_evidence_role",
        ),
        UniqueConstraint(
            "record_version_id",
            "verified_evidence_id",
            "mechanical_claim_id",
            name="uq_canonical_record_evidence_claim",
        ),
        Index(
            "uq_canonical_record_evidence_evidence_only",
            "record_version_id",
            "verified_evidence_id",
            unique=True,
            postgresql_where=text("mechanical_claim_id IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    record_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("canonical_record_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verified_evidence_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("catalog_verified_evidence.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mechanical_claim_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mechanical_claims.id", ondelete="RESTRICT"),
    )
    evidence_role: Mapped[str] = mapped_column(String(16), nullable=False, default="supports")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CanonicalConflict(Base):
    """Explicit review state for contradictory canonical evidence or claims."""

    __tablename__ = "canonical_conflicts"
    __table_args__ = (
        CheckConstraint(
            f"canonical_domain IN ({_CANONICAL_DOMAIN_SQL})",
            name="ck_canonical_conflicts_domain",
        ),
        CheckConstraint(
            "conflict_state IN ('open', 'resolved', 'blocked')",
            name="ck_canonical_conflicts_state",
        ),
        CheckConstraint(
            "resolution IS NULL OR resolution IN ('accepted_evidence', 'superseded', "
            "'duplicate', 'insufficient_evidence', 'not_applicable')",
            name="ck_canonical_conflicts_resolution",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    conflict_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    canonical_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    conflict_state: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    resolution: Mapped[str | None] = mapped_column(String(32))
    resolution_rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(128))


class CanonicalConflictItem(Base):
    """One contender in a conflict, backed by either a claim or publication evidence link."""

    __tablename__ = "canonical_conflict_items"
    __table_args__ = (
        CheckConstraint(
            "(mechanical_claim_id IS NOT NULL AND record_evidence_id IS NULL) OR "
            "(mechanical_claim_id IS NULL AND record_evidence_id IS NOT NULL)",
            name="ck_canonical_conflict_items_source",
        ),
        CheckConstraint(
            "disposition IN ('contender', 'selected', 'rejected', 'superseded')",
            name="ck_canonical_conflict_items_disposition",
        ),
        UniqueConstraint(
            "conflict_id",
            "mechanical_claim_id",
            name="uq_canonical_conflict_items_claim",
        ),
        UniqueConstraint(
            "conflict_id",
            "record_evidence_id",
            name="uq_canonical_conflict_items_evidence",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    conflict_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("canonical_conflicts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mechanical_claim_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mechanical_claims.id", ondelete="RESTRICT"),
    )
    record_evidence_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("canonical_record_evidence.id", ondelete="RESTRICT"),
    )
    disposition: Mapped[str] = mapped_column(String(16), nullable=False, default="contender")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
