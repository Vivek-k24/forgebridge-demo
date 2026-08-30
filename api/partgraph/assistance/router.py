from uuid import UUID

from fastapi import APIRouter

from ..auth.dependencies import AuthSessionDep, CurrentUserDep
from ..errors import ErrorEnvelope
from ..repair_session.guidance import RepairGuidanceRead, _guidance_view
from .schemas import AssistanceExplanationRead
from .service import explain_guidance

router = APIRouter(
    prefix="/api/v1/repair-sessions",
    tags=["Repair Assistance"],
    responses={
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
        500: {"model": ErrorEnvelope},
    },
)


@router.get(
    "/{session_id}/assistance/explanation",
    response_model=AssistanceExplanationRead,
)
async def deterministic_explanation(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> AssistanceExplanationRead:
    guidance = await _guidance_view(
        db,
        user_id=user.id,
        session_id=session_id,
        include_plan=False,
    )
    assert isinstance(guidance, RepairGuidanceRead)
    return explain_guidance(guidance)
