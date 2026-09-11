from fastapi import APIRouter

from ..errors import ErrorEnvelope
from ..identity.auth.dependencies import CurrentUserDep
from ..identity.auth.roles import require_role
from ..identity.auth.schemas import AdminAccessRead

router = APIRouter(
    prefix="/api/v1/operator",
    tags=["Operator"],
    responses={401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}},
)


@router.get("/access", response_model=AdminAccessRead)
async def access(user: CurrentUserDep) -> AdminAccessRead:
    require_role(user, {"operator_admin"})
    return AdminAccessRead()
