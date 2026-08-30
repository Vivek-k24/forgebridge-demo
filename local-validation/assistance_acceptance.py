from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select

from acceptance_runner import (
    API_URL,
    CaseContext,
    bind,
    create_session,
    create_vehicle,
    equal,
    guidance,
    headers,
    load_pool,
    progress,
    register,
    require,
    require_error,
    resolve_inventory,
    seed_definition,
    truth,
)
from partgraph.assistance.models import AIInvocation
from partgraph.database import session_factory

CONTRACT = "deterministic_assistance"


def explanation(ctx: CaseContext) -> dict[str, object]:
    body = require(
        ctx.client.get(
            f"/api/v1/repair-sessions/{ctx.session_id}/assistance/explanation"
        ),
        200,
        "deterministic assistance explanation",
    )
    equal(body["mode"], "deterministic", "assistance mode")
    equal(body["ai_invoked"], False, "deterministic explanation does not invoke AI")
    return body


async def ai_invocation_count(session_id: UUID) -> int:
    async with session_factory() as db:
        value = await db.scalar(
            select(func.count()).select_from(AIInvocation).where(
                AIInvocation.session_id == session_id
            )
        )
        return int(value or 0)


def main() -> None:
    vehicle = load_pool()[0]
    tag = f"assist{uuid4().hex[:8]}"
    device_id = str(uuid4())

    with httpx.Client(base_url=API_URL, timeout=10.0) as client:
        user_id = register(client, tag)
        vehicle_id, configuration_id = create_vehicle(client, tag, vehicle)
        session_id, _ = create_session(client, tag, vehicle_id, device_id)
        ctx = CaseContext(
            number=1201,
            scenario=CONTRACT,
            vehicle=vehicle,
            repair_template="headlamp-service",
            client=client,
            user_id=user_id,
            vehicle_id=vehicle_id,
            configuration_id=configuration_id,
            session_id=session_id,
            device_id=device_id,
        )
        ctx.seeded = asyncio.run(
            seed_definition(
                configuration_id,
                f"{tag}-supported",
                "headlamp-service",
                "diy_supported",
            )
        )
        bind(ctx)

        first = explanation(ctx)
        equal(first["guidance_status"], "action_available", "first explanation status")
        equal(first["reason_code"], "next_verified_action", "first explanation reason")
        equal(first["current_action"]["action_key"], "inspect", "first explained action")

        current = guidance(ctx)
        progress(
            ctx,
            current["current_action"]["action_id"],
            "completed",
            "assistance_inspect",
        )

        blocked = explanation(ctx)
        equal(
            blocked["guidance_status"],
            "inventory_blocked",
            "assistance mirrors Inventory blocking",
        )
        equal(
            blocked["reason_code"],
            "current_action_inventory_blocked",
            "assistance blocker reason",
        )
        truth(blocked["inventory_blockers"], "assistance exposes existing blockers")

        resolve_inventory(ctx, guidance(ctx), ordered_first=False)
        ready = explanation(ctx)
        equal(ready["guidance_status"], "action_available", "assistance after readiness")
        equal(ready["current_action"]["action_key"], "prepare", "assistance same current action")

        with httpx.Client(base_url=API_URL, timeout=10.0) as stranger:
            register(stranger, f"stranger{tag}"[:20])
            require_error(
                stranger.get(
                    f"/api/v1/repair-sessions/{ctx.session_id}/assistance/explanation"
                ),
                404,
                "REPAIR_SESSION_NOT_FOUND",
                "assistance owner isolation",
            )

        equal(
            asyncio.run(ai_invocation_count(session_id)),
            0,
            "deterministic assistance creates no AI audit row",
        )

        boundary_device = str(uuid4())
        boundary_session_id, _ = create_session(
            client,
            f"{tag}boundary",
            vehicle_id,
            boundary_device,
        )
        boundary_ctx = CaseContext(
            number=1202,
            scenario="assistance_prohibited_boundary",
            vehicle=vehicle,
            repair_template="headlamp-service",
            client=client,
            user_id=user_id,
            vehicle_id=vehicle_id,
            configuration_id=configuration_id,
            session_id=boundary_session_id,
            device_id=boundary_device,
        )
        boundary_ctx.seeded = asyncio.run(
            seed_definition(
                configuration_id,
                f"{tag}-prohibited",
                "headlamp-service",
                "guided_prohibited",
            )
        )
        bind(boundary_ctx)
        require_error(
            client.get(
                f"/api/v1/repair-sessions/{boundary_session_id}/assistance/explanation"
            ),
            403,
            "REPAIR_GUIDANCE_PROHIBITED",
            "assistance inherits prohibited guidance boundary",
        )

    print(f"WORKFLOW PASS: {CONTRACT}")
    print("RESULT: PASS — deterministic assistance mirrors verified state without AI.")


if __name__ == "__main__":
    main()
