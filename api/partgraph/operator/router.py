from uuid import UUID

from fastapi import APIRouter, Depends, status

from ..errors import ErrorEnvelope
from ..identity.auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from ..identity.auth.roles import require_role
from ..identity.auth.schemas import AdminAccessRead
from .schemas import OperatorAuditRead, PreviewOperatorBootstrapStatus, ProviderCreate, ProviderRead, ProviderUpdate
from .service import (
    bootstrap_preview_operator,
    create_provider,
    list_operator_audit,
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


def _operator(user: CurrentUserDep):
    return require_role(user, {"operator_admin"})


@router.get("/access", response_model=AdminAccessRead)
async def access(user: CurrentUserDep) -> AdminAccessRead:
    _operator(user)
    return AdminAccessRead()


@router.get("/preview-bootstrap/status", response_model=PreviewOperatorBootstrapStatus)
async def preview_bootstrap_status(
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> PreviewOperatorBootstrapStatus:
    del user
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
    await bootstrap_preview_operator(session, user=user)
    return AdminAccessRead()


@router.get("/providers", response_model=list[ProviderRead])
async def providers(user: CurrentUserDep, session: AuthSessionDep) -> list[ProviderRead]:
    _operator(user)
    return await list_providers(session)


@router.get("/audit", response_model=list[OperatorAuditRead])
async def audit(user: CurrentUserDep, session: AuthSessionDep) -> list[OperatorAuditRead]:
    _operator(user)
    return await list_operator_audit(session)


@router.post(
    "/providers",
    response_model=ProviderRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def add_provider(
    payload: ProviderCreate,
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> ProviderRead:
    operator = _operator(user)
    return await create_provider(session, actor_id=operator.id, payload=payload)


@router.patch(
    "/providers/{provider_id}",
    response_model=ProviderRead,
    dependencies=[CsrfDep],
)
async def change_provider(
    provider_id: UUID,
    payload: ProviderUpdate,
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> ProviderRead:
    operator = _operator(user)
    return await update_provider(
        session,
        actor_id=operator.id,
        provider_id=provider_id,
        payload=payload,
    )
