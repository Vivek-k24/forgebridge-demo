from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class PartFitment(Base):
    """Exact-configuration applicability, exclusion, or qualified fitment for a part role."""

    __tablename__ = "part_fitments"
    __table_args__ = (
        CheckConstraint(
            "applicability_state IN ('applicable', 'excluded', 'conditional')",
            name="ck_part_fitments_state",
        ),
        CheckConstraint(
            "applicability_state <> 'conditional' OR qualifier_key <> ''",
            name="ck_part_fitments_conditional_key",
        ),
        UniqueConstraint(
            "vehicle_configuration_id",
            "component_part_role_id",
            "qualifier_key",
            name="uq_part_fitments_vehicle_role_qualifier",
        ),
        Index(
            "ix_part_fitments_vehicle_state",
            "vehicle_configuration_id",
            "applicability_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    component_part_role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("component_part_roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    applicability_state: Mapped[str] = mapped_column(String(16), nullable=False)
    qualifier_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    qualifiers: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
