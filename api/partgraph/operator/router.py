from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from ..errors import ErrorEnvelope
from ..identity.auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from ..identity.auth.roles import (
    OperatorAdminDep,
    assume_operator_database_role,
)
from ..identity.auth.schemas import AdminAccessRead
from .local_bootstrap import (
    bootstrap_local_operator,
    local_operator_bootstrap_environment,
    local_operator_bootstrap_status,
)
from .nhtsa import stage_nhtsa_recall_query
from .preview_bootstrap import (
    bootstrap_preview_operator,
    preview_operator_bootstrap_authorized,
    preview_operator_bootstrap_status,
)
from .reference_parts import stage_reference_parts_dataset
from .schemas import (
    CatalogSourceCreate,
    CatalogSourceRead,
    CatalogSourceUpdate,
    NhtsaRecallStageRead,
    NhtsaRecallStageRequest,
    OperatorAuditRead,
    OperatorUserRead,
    PreviewOperatorBootstrapStatus,
    ProviderCreate,
    ProviderRead,
    ProviderSourceBindingCreate,
    ProviderSourceBindingRead,
    ProviderSourceBindingUpdate,
    ProviderUpdate,
    ReferencePartsStageRead,
    ReferencePartsStageRequest,
    UserRoleUpdate,
)
from .service import (
    change_user_role,
    create_catalog_source,
    create_provider,
    create_provider_source_binding,
    list_catalog_sources,
    list_operator_audit,
    list_operator_users,
    list_provider_source_bindings,
    list_providers,
    update_catalog_source,
    update_provider,
    update_provider_source_binding,
)

router = APIRouter(
    prefix="/api/v1/operator",
    tags=["Operator"],
    responses={401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}},
)
CsrfDep = Depends(require_csrf)


@router.get("/access", response_model=AdminAccessRead)
async def access(user: OperatorAdminDep) -> AdminAccessRead:
    del user
    return AdminAccessRead()


@router.get("/preview-bootstrap/status", response_model=PreviewOperatorBootstrapStatus)
async def preview_bootstrap_status(
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> PreviewOperatorBootstrapStatus:
    if local_operator_bootstrap_environment():
        return await local_operator_bootstrap_status(session)
    return await preview_operator_bootstrap_status(session, user=user)


@router.post(
    "/preview-bootstrap",
    response_model=AdminAccessRead,
    dependencies=[CsrfDep],
)
async def preview_bootstrap(
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> AdminAccessRead:
    if local_operator_bootstrap_environment():
        await assume_operator_database_role(session)
        await bootstrap_local_operator(session, user=user)
    else:
        if preview_operator_bootstrap_authorized(user):
            await assume_operator_database_role(session)
        await bootstrap_preview_operator(session, user=user)
    return AdminAccessRead()


@router.get("/users", response_model=list[OperatorUserRead])
async def users(
    user: OperatorAdminDep,
    session: AuthSessionDep,
    limit: Annotated[int, Query(ge=1, le=250)] = 100,
) -> list[OperatorUserRead]:
    await assume_operator_database_role(session)
    del user
    return await list_operator_users(session, limit=limit)


@router.patch(
    "/users/{user_id}/role",
    response_model=OperatorUserRead,
    dependencies=[CsrfDep],
)
async def change_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    user: OperatorAdminDep,
    session: AuthSessionDep,
) -> OperatorUserRead:
    await assume_operator_database_role(session)
    return await change_user_role(
        session,
        actor_id=user.id,
        target_user_id=user_id,
        payload=payload,
    )


@router.get("/providers", response_model=list[ProviderRead])
async def providers(user: OperatorAdminDep, session: AuthSessionDep) -> list[ProviderRead]:
    await assume_operator_database_role(session)
    del user
    return await list_providers(session)


@router.post(
    "/providers",
    response_model=ProviderRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def add_provider(
    payload: ProviderCreate,
    user: OperatorAdminDep,
    session: AuthSessionDep,
) -> ProviderRead:
    await assume_operator_database_role(session)
    return await create_provider(session, actor_id=user.id, payload=payload)


@router.patch(
    "/providers/{provider_id}",
    response_model=ProviderRead,
    dependencies=[CsrfDep],
)
async def change_provider(
    provider_id: UUID,
    payload: ProviderUpdate,
    user: OperatorAdminDep,
    session: AuthSessionDep,
) -> ProviderRead:
    await assume_operator_database_role(session)
    return await update_provider(
        session,
        actor_id=user.id,
        provider_id=provider_id,
        payload=payload,
    )


@router.get("/sources", response_model=list[CatalogSourceRead])
async def sources(user: OperatorAdminDep, session: AuthSessionDep) -> list[CatalogSourceRead]:
    await assume_operator_database_role(session)
    del user
    return await list_catalog_sources(session)


@router.post(
    "/sources",
    response_model=CatalogSourceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def add_source(
    payload: CatalogSourceCreate,
    user: OperatorAdminDep,
    session: AuthSessionDep,
) -> CatalogSourceRead:
    await assume_operator_database_role(session)
    return await create_catalog_source(session, actor_id=user.id, payload=payload)


@router.patch(
    "/sources/{source_id}",
    response_model=CatalogSourceRead,
    dependencies=[CsrfDep],
)
async def change_source(
    source_id: UUID,
    payload: CatalogSourceUpdate,
    user: OperatorAdminDep,
    session: AuthSessionDep,
) -> CatalogSourceRead:
    await assume_operator_database_role(session)
    return await update_catalog_source(
        session,
        actor_id=user.id,
        source_id=source_id,
        payload=payload,
    )


@router.get(
    "/provider-source-bindings",
    response_model=list[ProviderSourceBindingRead],
)
async def provider_source_bindings(
    user: OperatorAdminDep,
    session: AuthSessionDep,
) -> list[ProviderSourceBindingRead]:
    await assume_operator_database_role(session)
    del user
    return await list_provider_source_bindings(session)


@router.post(
    "/provider-source-bindings",
    response_model=ProviderSourceBindingRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def add_provider_source_binding(
    payload: ProviderSourceBindingCreate,
    user: OperatorAdminDep,
    session: AuthSessionDep,
) -> ProviderSourceBindingRead:
    await assume_operator_database_role(session)
    return await create_provider_source_binding(
        session,
        actor_id=user.id,
        payload=payload,
    )


@router.patch(
    "/provider-source-bindings/{binding_id}",
    response_model=ProviderSourceBindingRead,
    dependencies=[CsrfDep],
)
async def change_provider_source_binding(
    binding_id: UUID,
    payload: ProviderSourceBindingUpdate,
    user: OperatorAdminDep,
    session: AuthSessionDep,
) -> ProviderSourceBindingRead:
    await assume_operator_database_role(session)
    return await update_provider_source_binding(
        session,
        actor_id=user.id,
        binding_id=binding_id,
        payload=payload,
    )


@router.post(
    "/reference-parts/stage",
    response_model=ReferencePartsStageRead,
    dependencies=[CsrfDep],
)
async def stage_reference_parts(
    payload: ReferencePartsStageRequest,
    user: OperatorAdminDep,
    session: AuthSessionDep,
) -> ReferencePartsStageRead:
    await assume_operator_database_role(session)
    return await stage_reference_parts_dataset(
        session,
        actor_id=user.id,
        payload=payload,
    )


@router.post(
    "/nhtsa/recalls/stage",
    response_model=NhtsaRecallStageRead,
    dependencies=[CsrfDep],
)
async def stage_nhtsa_recalls(
    payload: NhtsaRecallStageRequest,
    user: OperatorAdminDep,
    session: AuthSessionDep,
) -> NhtsaRecallStageRead:
    await assume_operator_database_role(session)
    return await stage_nhtsa_recall_query(
        session,
        actor_id=user.id,
        payload=payload,
    )


@router.get("/audit", response_model=list[OperatorAuditRead])
async def audit(user: OperatorAdminDep, session: AuthSessionDep) -> list[OperatorAuditRead]:
    await assume_operator_database_role(session)
    del user
    return await list_operator_audit(session)
