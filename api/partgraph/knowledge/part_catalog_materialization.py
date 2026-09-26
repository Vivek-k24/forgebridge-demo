from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .parts import ComponentDefinition, ComponentPartRole, PartIdentity
from .repair_materialization_contract import invalid_materialization


class ComponentIdentitySpec(BaseModel):
    component_key: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=180)

    @model_validator(mode="after")
    def normalize_values(self) -> ComponentIdentitySpec:
        self.component_key = " ".join(self.component_key.split())
        self.display_name = " ".join(self.display_name.split())
        if not self.component_key or not self.display_name:
            raise ValueError("component identity fields cannot be blank")
        return self


class PartIdentitySpec(BaseModel):
    manufacturer: str = Field(min_length=1, max_length=96)
    part_number: str = Field(min_length=1, max_length=96)
    revision: str = Field(default="", max_length=64)
    display_name: str = Field(min_length=1, max_length=180)

    @model_validator(mode="after")
    def normalize_values(self) -> PartIdentitySpec:
        self.manufacturer = " ".join(self.manufacturer.split())
        self.part_number = " ".join(self.part_number.split())
        self.revision = " ".join(self.revision.split())
        self.display_name = " ".join(self.display_name.split())
        if not self.manufacturer or not self.part_number or not self.display_name:
            raise ValueError("part identity fields cannot be blank")
        return self


class PartFitmentMaterializationPayload(BaseModel):
    component_part_role_id: UUID | None = None
    component: ComponentIdentitySpec | None = None
    part: PartIdentitySpec | None = None
    position_key: str = Field(default="", max_length=96)
    applicability_state: Literal["applicable", "excluded", "conditional"]
    qualifier_key: str = Field(default="", max_length=128)
    qualifiers: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_identity_mode(self) -> PartFitmentMaterializationPayload:
        self.position_key = self.position_key.strip()
        self.qualifier_key = self.qualifier_key.strip()
        has_inline_identity = self.component is not None or self.part is not None
        if self.component_part_role_id is not None:
            if has_inline_identity or self.position_key:
                raise ValueError(
                    "component_part_role_id cannot be combined with inline part identity"
                )
        elif self.component is None or self.part is None:
            raise ValueError(
                "part fitment requires component_part_role_id or complete inline part identity"
            )
        if self.applicability_state == "conditional" and not self.qualifier_key:
            raise ValueError("conditional fitment requires qualifier_key")
        return self


@dataclass(frozen=True, slots=True)
class ResolvedPartFitmentPayload:
    component_part_role_id: UUID
    applicability_state: Literal["applicable", "excluded", "conditional"]
    qualifier_key: str
    qualifiers: dict[str, object]


async def resolve_part_fitment_claim_payload(
    db: AsyncSession,
    raw_payload: dict[str, object],
) -> ResolvedPartFitmentPayload:
    try:
        payload = PartFitmentMaterializationPayload.model_validate(raw_payload)
    except ValidationError as exc:
        raise invalid_materialization(
            "Part-fitment claim payload is invalid.",
            details={"validation": exc.errors(include_url=False)},
        ) from exc

    if payload.component_part_role_id is not None:
        role = await db.get(ComponentPartRole, payload.component_part_role_id)
        if role is None:
            raise invalid_materialization(
                "Part-fitment claim references an unknown canonical component/part role."
            )
        return ResolvedPartFitmentPayload(
            component_part_role_id=role.id,
            applicability_state=payload.applicability_state,
            qualifier_key=payload.qualifier_key,
            qualifiers=payload.qualifiers,
        )

    assert payload.component is not None
    assert payload.part is not None
    identity_lock = "\x1f".join(
        (
            payload.component.component_key,
            payload.part.manufacturer,
            payload.part.part_number,
            payload.part.revision,
            payload.position_key,
        )
    )
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"canonical-part-role:{identity_lock}"},
    )

    component = await db.scalar(
        select(ComponentDefinition).where(
            ComponentDefinition.component_key == payload.component.component_key
        )
    )
    if component is None:
        component = ComponentDefinition(
            id=uuid4(),
            component_key=payload.component.component_key,
            display_name=payload.component.display_name,
        )
        db.add(component)
        await db.flush()
    elif component.display_name != payload.component.display_name:
        raise invalid_materialization(
            "Inline fitment identity reuses an existing component key with a different display name."
        )

    part = await db.scalar(
        select(PartIdentity).where(
            PartIdentity.manufacturer == payload.part.manufacturer,
            PartIdentity.part_number == payload.part.part_number,
            PartIdentity.revision == payload.part.revision,
        )
    )
    if part is None:
        part = PartIdentity(
            id=uuid4(),
            manufacturer=payload.part.manufacturer,
            part_number=payload.part.part_number,
            revision=payload.part.revision,
            display_name=payload.part.display_name,
        )
        db.add(part)
        await db.flush()

    role = await db.scalar(
        select(ComponentPartRole).where(
            ComponentPartRole.component_id == component.id,
            ComponentPartRole.part_id == part.id,
            ComponentPartRole.position_key == payload.position_key,
        )
    )
    if role is None:
        role = ComponentPartRole(
            id=uuid4(),
            component_id=component.id,
            part_id=part.id,
            position_key=payload.position_key,
        )
        db.add(role)
        await db.flush()

    return ResolvedPartFitmentPayload(
        component_part_role_id=role.id,
        applicability_state=payload.applicability_state,
        qualifier_key=payload.qualifier_key,
        qualifiers=payload.qualifiers,
    )
