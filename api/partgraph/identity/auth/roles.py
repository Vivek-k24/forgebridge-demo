from fastapi import status

from ..errors import ErrorCode, PartGraphError
from .dependencies import CurrentUserDep
from .models import User


def require_role(user: CurrentUserDep, allowed_roles: set[str]) -> User:
    if user.role not in allowed_roles:
        raise PartGraphError(
            code=ErrorCode.AUTH_ADMIN_REQUIRED,
            message="This account does not have access to this area.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return user
