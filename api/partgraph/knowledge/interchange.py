from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class PartRelationship(Base):
    """Directed replacement/supersession relation or symmetric interchange assertion."""

    __tablename__ = "part_relationships"
    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('supersedes', 'service_replacement', 'interchange')",
            name="ck_part_relationships_type",
        ),
        CheckConstraint(
            "source_part_id <> target_part_id",
            name="ck_part_relationships_distinct_parts",
        ),
        UniqueConstraint(
            "source_part_id",
            "target_part_id",
            "relationship_type",
            name="uq_part_relationships_edge",
        ),
        Index(
            "ix_part_relationships_target_type",
            "target_part_id",
            "relationship_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_part_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("part_identities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    target_part_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("part_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
