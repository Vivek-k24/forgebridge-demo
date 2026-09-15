from typing import Annotated

from fastapi import APIRouter, Depends, Header

from ..errors import ErrorEnvelope
from ..identity.auth.dependencies import AuthSessionDep, require_csrf
from ..identity.auth.roles import CuratorUserDep, assume_materializer_database_role
from .canonical_claim_materialization import router as canonical_claim_materialization_router
from .downstream_materialization import (
    DownstreamRequirementMaterializationCreate,
    DownstreamRequirementMaterializationRead,
    materialize_downstream_requirement_service,
)
from .repair_materialization_contract import (
    IDEMPOTENCY_PATTERN,
    RepairDefinitionMaterializationCreate,
    RepairDefinitionMaterializationRead,
    invalid_materialization,
)
from .repair_materialization_service import materialize_repair_definition_service
from .vehicle_domain_materialization import router as vehicle_domain_materialization_router

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$",
    ),
]

router = APIRouter(
    prefix="/api/v1/curation",
    tags=["Knowledge Curation"],
    responses={
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
        500: {"model": ErrorEnvelope},
    },
)
router.include_router(canonical_claim_materialization_router)
router.include_router(vehicle_domain_materialization_router)
CsrfDep = Depends(require_csrf)


@router.post(
    "/repair-definitions/materialize",
    response_model=RepairDefinitionMaterializationRead,
    dependencies=[CsrfDep],
)
async def materialize_repair_definition(
    request: RepairDefinitionMaterializationCreate,
    user: CuratorUserDep,
    db: AuthSessionDep,
    idempotency_key: IdempotencyKey,
) -> RepairDefinitionMaterializationRead:
    await assume_materializer_database_role(db)
    if IDEMPOTENCY_PATTERN.fullmatch(idempotency_key) is None:
        raise invalid_materialization("Idempotency-Key is invalid.")
    return await materialize_repair_definition_service(
        db,
        request=request,
        actor=f"{user.id}:{user.role}",
        idempotency_key=idempotency_key,
    )


@router.post(
    "/repair-definitions/downstream/materialize",
    response_model=DownstreamRequirementMaterializationRead,
    dependencies=[CsrfDep],
)
async def materialize_downstream_requirement(
    request: DownstreamRequirementMaterializationCreate,
    user: CuratorUserDep,
    db: AuthSessionDep,
) -> DownstreamRequirementMaterializationRead:
    del user
    await assume_materializer_database_role(db)
    return await materialize_downstream_requirement_service(
        db,
        request=request,
    )