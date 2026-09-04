import asyncio
from types import SimpleNamespace

import partgraph.knowledge.workbench_service as workbench_service
from partgraph.database import session_factory

BATCH_KEY = "selected-asian-1996-2000-v1"


def _enable_workbench(monkeypatch) -> None:
    monkeypatch.setattr(
        workbench_service,
        "settings",
        SimpleNamespace(workbench_enabled=True),
    )


def test_workbench_dashboard_keeps_candidates_separate_from_collection(monkeypatch) -> None:
    _enable_workbench(monkeypatch)

    async def run() -> None:
        async with session_factory() as session:
            dashboard = await workbench_service.workbench_dashboard(session, BATCH_KEY)

        assert dashboard.candidates == 363
        assert dashboard.collected == 0
        assert dashboard.verified == 0
        assert dashboard.collection_percent == 0.0
        assert dashboard.verification_percent == 0.0
        assert {item.make: item.candidates for item in dashboard.makes} == {
            "Acura": 62,
            "Honda": 114,
            "Lexus": 18,
            "Subaru": 63,
            "Toyota": 106,
        }

    asyncio.run(run())


def test_make_job_can_pause_and_resume_same_checkpoint(monkeypatch) -> None:
    _enable_workbench(monkeypatch)

    async def run() -> None:
        async with session_factory() as session:
            started = await workbench_service.start_make_job(session, BATCH_KEY, "Lexus")
        assert started.make == "Lexus"
        assert started.status == "queued"
        assert started.total_items == 18
        assert started.cursor_position == 0

        async with session_factory() as session:
            paused = await workbench_service.pause_make_job(session, BATCH_KEY, "Lexus")
        assert paused.id == started.id
        assert paused.status == "paused"
        assert paused.cursor_position == started.cursor_position

        async with session_factory() as session:
            resumed = await workbench_service.resume_make_job(session, BATCH_KEY, "Lexus")
        assert resumed.id == started.id
        assert resumed.status == "queued"
        assert resumed.cursor_position == started.cursor_position

    asyncio.run(run())
