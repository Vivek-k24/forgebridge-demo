from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, status

from ..errors import ErrorCode, PartGraphError
from .dependencies import CurrentUserDep
from .models import User

REVIEW_ROLES = frozenset({"reviewer", "curator", "operator_admin"})
CURATION_PUBLISH_ROLES = frozenset({"curator", "operator_admin"})
CONTRIBUTION_ROLES = frozenset({"contributor", "reviewer", "curator", "operator_admin"})


def require_any_role(*allowed_roles: str) -> Callable[[CurrentUserDep], User]:
    allowed = frozenset(allowed_roles)
    if not allowed:
        raise ValueError("At least one role is required.")

    async def dependency(user: CurrentUserDep) -> User:
        if user.role not in allowed:
            raise PartGraphError(
                code=ErrorCode.RBAC_ROLE_REQUIRED,
                message="Your account role is not authorized for this operation.",
                status_code=status.HTTP_403_FORBIDDEN,
                details={"allowed_roles": sorted(allowed)},
            )
        return user

    return dependency


def require_role(role: str) -> Callable[[CurrentUserDep], User]:
    return require_any_role(role)


ReviewerUserDep = Annotated[
    User,
    Depends(require_any_role(*sorted(REVIEW_ROLES))),
]
CuratorUserDep = Annotated[
    User,
    Depends(require_any_role(*sorted(CURATION_PUBLISH_ROLES))),
]
ContributorUserDep = Annotated[
    User,
    Depends(require_any_role(*sorted(CONTRIBUTION_ROLES))),
]
OperatorAdminDep = Annotated[User, Depends(require_role("operator_admin"))]
