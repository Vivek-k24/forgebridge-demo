from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from ..errors import ErrorEnvelope
from ..identity.auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from ..identity.auth.roles import OperatorAdminDep
from ..identity.auth.schemas import AdminAccessRead
from .local_bootstrap import (
    bootstrap_local_operator,
    local_operator_bootstrap_environment,
    local_operator_bootstrap_status,
)
from .schemas import (
    OperatorAuditRead,
    OperatorUserRead,
    PreviewOperatorBootstrapStatus,
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
    UserRoleUpdate,
)
from .service import (
    bootstrap_preview_operator,
    change_user_role,
    create_provider,
    list_operator_audit,
    list_operator_users,
    list_providers,
    preview_operator_bootstrap_status,
    update_provider,
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
    del user
    if local_operator_bootstrap_environment():
        return await local_operator_bootstrap_status(session)
    return await preview_operator_bootstrap_status(session)


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
        await bootstrap_local_operator(session, user=user)
    else:
        await bootstrap_preview_operator(session, user=user)
    return AdminAccessRead()


@router.get("/users", response_model=list[OperatorUserRead])
async def users(
    user: OperatorAdminDep,
    session: AuthSessionDep,
    limit: Annotated[int, Query(ge=1, le=250)] = 100,
) -> list[OperatorUserRead]:
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
    return await change_user_role(
        session,
        actor_id=user.id,
        target_user_id=user_id,
        payload=payload,
    )


@router.get("/providers", response_model=list[ProviderRead])
async def providers(user: OperatorAdminDep, session: AuthSessionDep) -> list[ProviderRead]:
    del user
    return await list_providers(session)


@router.get("/audit", response_model=list[OperatorAuditRead])
async def audit(user: OperatorAdminDep, session: AuthSessionDep) -> list[OperatorAuditRead]:
    del user
    return await list_operator_audit(session)


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
    return await update_provider(
        session,
        actor_id=user.id,
        provider_id=provider_id,
        payload=payload,
    )
