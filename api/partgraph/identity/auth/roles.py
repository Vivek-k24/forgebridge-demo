from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from .dependencies import CurrentUserDep
from .models import User

REVIEW_ROLES = frozenset({"reviewer", "curator", "operator_admin"})
CURATION_PUBLISH_ROLES = frozenset({"curator", "operator_admin"})
CONTRIBUTION_ROLES = frozenset({"contributor", "reviewer", "curator", "operator_admin"})
REVIEWER_DATABASE_ROLE = "partgraph_reviewer"
CONTRIBUTOR_DATABASE_ROLE = "partgraph_contributor"
CURATOR_DATABASE_ROLE = "partgraph_curator"
MATERIALIZER_DATABASE_ROLE = "partgraph_materializer"
INGESTOR_DATABASE_ROLE = "partgraph_ingestor"
OPERATOR_DATABASE_ROLE = "partgraph_operator"


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


async def _assume_database_role(session: AsyncSession, role: str) -> None:
    await session.execute(text(f"SET LOCAL ROLE {role}"))


async def assume_reviewer_database_role(session: AsyncSession) -> None:
    """Narrow the current transaction to the reviewer database privilege set."""
    await _assume_database_role(session, REVIEWER_DATABASE_ROLE)


async def assume_contributor_database_role(session: AsyncSession) -> None:
    """Narrow the transaction to staging-only candidate submission privileges."""
    await _assume_database_role(session, CONTRIBUTOR_DATABASE_ROLE)


async def assume_curator_database_role(session: AsyncSession) -> None:
    """Narrow the transaction to normalized-claim/conflict curation privileges."""
    await _assume_database_role(session, CURATOR_DATABASE_ROLE)


async def assume_materializer_database_role(session: AsyncSession) -> None:
    """Narrow a curator-authorized transaction to versioned repair publication."""
    await _assume_database_role(session, MATERIALIZER_DATABASE_ROLE)


async def assume_ingestor_database_role(session: AsyncSession) -> None:
    """Narrow provider acquisition to bound-source reads and candidate staging only."""
    await _assume_database_role(session, INGESTOR_DATABASE_ROLE)


async def assume_operator_database_role(session: AsyncSession) -> None:
    """Narrow an authorized operator transaction to operator configuration privileges."""
    await _assume_database_role(session, OPERATOR_DATABASE_ROLE)


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
