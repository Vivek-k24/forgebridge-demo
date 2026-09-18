import os
import unittest
from io import BytesIO
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import select, text

from partgraph.database import session_factory
from partgraph.identity.auth.models import User
from partgraph.identity.auth.service import set_user_context
from partgraph.identity.user_vehicle.models import UserVehicle
from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.knowledge.models import RepairDefinition  # noqa: F401
from partgraph.repair_experience.memory.models import RepairPhotoEvidence
from partgraph.repair_experience.memory.photo_lifecycle import (
    MEDIA_WORKER_ROLE,
    _assume_media_worker,
    create_photo,
    cron_request_authorized,
    delete_photo,
    reconcile_photo_storage_row,
)
from partgraph.repair_experience.service import create_repair_session
from reference_fixture_support import primary_vehicle_id, primary_vehicle_snapshot

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
REFERENCE_VEHICLE_ID = primary_vehicle_id()
REFERENCE_VEHICLE = primary_vehicle_snapshot()
MAX_PHOTO_BYTES = 4 * 1024 * 1024


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), (30, 60, 90)).save(output, format="PNG")
    return output.getvalue()


class PhotoStorageRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.user_id = uuid4()
        self.user_vehicle_id = uuid4()
        suffix = uuid4().hex[:12]
        self.device_id = uuid4()
        async with session_factory() as db:
            async with db.begin():
                vehicle = await db.get(VehicleConfiguration, REFERENCE_VEHICLE_ID)
                if vehicle is None:
                    raise unittest.SkipTest("Reference vehicle fixture is not available")
                user = User(
                    id=self.user_id,
                    email=f"photo-storage-{suffix}@example.invalid",
                    username=f"photo_storage_{suffix}",
                    password_hash="photo-storage-fixture",
                    role="owner",
                    is_active=True,
                )
                user_vehicle = UserVehicle(
                    id=self.user_vehicle_id,
                    user_id=self.user_id,
                    canonical_configuration_id=REFERENCE_VEHICLE_ID,
                    nickname="Photo storage fixture",
                    identity_source="manual",
                    identity_resolution="matched",
                    identity_snapshot=dict(REFERENCE_VEHICLE),
                )
                db.add_all([user, user_vehicle])
                await db.flush()
                await db.execute(text("SET LOCAL ROLE partgraph_app"))
                await set_user_context(db, self.user_id)
                bundle = await create_repair_session(
                    db,
                    user_id=self.user_id,
                    user_vehicle_id=self.user_vehicle_id,
                    title="Photo storage durability fixture",
                    device_id=self.device_id,
                    idempotency_key=f"photo_storage_session_{suffix}",
                )
                self.session_id = bundle.repair_session.id

    async def _owner_context(self, db) -> None:
        await db.execute(text("SET LOCAL ROLE partgraph_app"))
        await set_user_context(db, self.user_id)

    async def _create_photo(self, *, idempotency_key: str) -> UUID:
        async with session_factory() as db:
            async with db.begin():
                await self._owner_context(db)
                result = await create_photo(
                    db,
                    user_id=self.user_id,
                    session_id=self.session_id,
                    device_id=self.device_id,
                    idempotency_key=idempotency_key,
                    purpose="general",
                    observation_id=None,
                    fastener_id=None,
                    filename="fixture.png",
                    data=_png_bytes(),
                    maximum_bytes=MAX_PHOTO_BYTES,
                )
                return result.id

    async def _worker_row(self, photo_id: UUID) -> RepairPhotoEvidence | None:
        async with session_factory() as db:
            async with db.begin():
                await _assume_media_worker(db)
                return await db.scalar(
                    select(RepairPhotoEvidence).where(RepairPhotoEvidence.id == photo_id)
                )

    async def _reconcile_upload_ready(self, photo_id: UUID) -> None:
        with patch(
            "partgraph.repair_experience.memory.photo_lifecycle.store_photo",
            new=AsyncMock(),
        ):
            async with session_factory() as db:
                async with db.begin():
                    await _assume_media_worker(db)
                    row = await db.scalar(
                        select(RepairPhotoEvidence)
                        .where(RepairPhotoEvidence.id == photo_id)
                        .with_for_update()
                    )
                    assert row is not None
                    self.assertEqual(await reconcile_photo_storage_row(db, row), "ready")

    async def test_create_rollback_cannot_leave_untracked_blob(self) -> None:
        store = AsyncMock()
        db = session_factory()
        transaction = await db.begin()
        try:
            await self._owner_context(db)
            with patch(
                "partgraph.repair_experience.memory.photo_lifecycle.store_photo",
                new=store,
            ):
                result = await create_photo(
                    db,
                    user_id=self.user_id,
                    session_id=self.session_id,
                    device_id=self.device_id,
                    idempotency_key=f"photo_create_rollback_{uuid4().hex}",
                    purpose="general",
                    observation_id=None,
                    fastener_id=None,
                    filename="rollback.png",
                    data=_png_bytes(),
                    maximum_bytes=MAX_PHOTO_BYTES,
                )
                photo_id = result.id
            await transaction.rollback()
        finally:
            await db.close()

        store.assert_not_awaited()
        self.assertIsNone(await self._worker_row(photo_id))

    async def test_upload_reconcile_is_retryable_after_commit_loss(self) -> None:
        photo_id = await self._create_photo(
            idempotency_key=f"photo_upload_retry_{uuid4().hex}"
        )
        initial = await self._worker_row(photo_id)
        assert initial is not None
        self.assertEqual(initial.storage_state, "pending_upload")
        self.assertIsNotNone(initial.pending_content)

        store = AsyncMock()
        db = session_factory()
        transaction = await db.begin()
        try:
            await _assume_media_worker(db)
            row = await db.scalar(
                select(RepairPhotoEvidence)
                .where(RepairPhotoEvidence.id == photo_id)
                .with_for_update()
            )
            assert row is not None
            with patch(
                "partgraph.repair_experience.memory.photo_lifecycle.store_photo",
                new=store,
            ):
                self.assertEqual(await reconcile_photo_storage_row(db, row), "ready")
            # Simulate acknowledgement/commit loss after the blob write succeeded.
            await transaction.rollback()
        finally:
            await db.close()

        after_loss = await self._worker_row(photo_id)
        assert after_loss is not None
        self.assertEqual(after_loss.storage_state, "pending_upload")
        self.assertIsNotNone(after_loss.pending_content)

        async with session_factory() as db:
            async with db.begin():
                await _assume_media_worker(db)
                row = await db.scalar(
                    select(RepairPhotoEvidence)
                    .where(RepairPhotoEvidence.id == photo_id)
                    .with_for_update()
                )
                assert row is not None
                with patch(
                    "partgraph.repair_experience.memory.photo_lifecycle.store_photo",
                    new=store,
                ):
                    self.assertEqual(await reconcile_photo_storage_row(db, row), "ready")

        self.assertEqual(store.await_count, 2)
        ready = await self._worker_row(photo_id)
        assert ready is not None
        self.assertEqual(ready.storage_state, "ready")
        self.assertIsNone(ready.pending_content)
        self.assertEqual(ready.storage_attempts, 1)

    async def test_delete_tombstone_precedes_idempotent_blob_removal(self) -> None:
        photo_id = await self._create_photo(
            idempotency_key=f"photo_delete_fixture_{uuid4().hex}"
        )
        await self._reconcile_upload_ready(photo_id)

        delete_storage = AsyncMock()
        db = session_factory()
        transaction = await db.begin()
        try:
            await self._owner_context(db)
            with patch(
                "partgraph.repair_experience.memory.photo_lifecycle.delete_photo_file",
                new=delete_storage,
            ):
                await delete_photo(
                    db,
                    user_id=self.user_id,
                    session_id=self.session_id,
                    photo_id=photo_id,
                    device_id=self.device_id,
                    idempotency_key=f"photo_delete_rollback_{uuid4().hex}",
                )
            await transaction.rollback()
        finally:
            await db.close()

        delete_storage.assert_not_awaited()
        still_live = await self._worker_row(photo_id)
        assert still_live is not None
        self.assertEqual(still_live.storage_state, "ready")
        self.assertIsNone(still_live.deleted_at)

        async with session_factory() as db:
            async with db.begin():
                await self._owner_context(db)
                with patch(
                    "partgraph.repair_experience.memory.photo_lifecycle.delete_photo_file",
                    new=delete_storage,
                ):
                    await delete_photo(
                        db,
                        user_id=self.user_id,
                        session_id=self.session_id,
                        photo_id=photo_id,
                        device_id=self.device_id,
                        idempotency_key=f"photo_delete_commit_{uuid4().hex}",
                    )
        delete_storage.assert_not_awaited()
        tombstone = await self._worker_row(photo_id)
        assert tombstone is not None
        self.assertEqual(tombstone.storage_state, "delete_pending")
        self.assertIsNotNone(tombstone.deleted_at)

        db = session_factory()
        transaction = await db.begin()
        try:
            await _assume_media_worker(db)
            row = await db.scalar(
                select(RepairPhotoEvidence)
                .where(RepairPhotoEvidence.id == photo_id)
                .with_for_update()
            )
            assert row is not None
            with patch(
                "partgraph.repair_experience.memory.photo_lifecycle.delete_photo_file",
                new=delete_storage,
            ):
                self.assertEqual(await reconcile_photo_storage_row(db, row), "deleted")
            # Blob removal happened, but this worker transaction loses its commit.
            await transaction.rollback()
        finally:
            await db.close()

        after_loss = await self._worker_row(photo_id)
        assert after_loss is not None
        self.assertEqual(after_loss.storage_state, "delete_pending")
        self.assertIsNotNone(after_loss.deleted_at)

        async with session_factory() as db:
            async with db.begin():
                await _assume_media_worker(db)
                row = await db.scalar(
                    select(RepairPhotoEvidence)
                    .where(RepairPhotoEvidence.id == photo_id)
                    .with_for_update()
                )
                assert row is not None
                with patch(
                    "partgraph.repair_experience.memory.photo_lifecycle.delete_photo_file",
                    new=delete_storage,
                ):
                    self.assertEqual(await reconcile_photo_storage_row(db, row), "deleted")

        self.assertEqual(delete_storage.await_count, 2)
        deleted = await self._worker_row(photo_id)
        assert deleted is not None
        self.assertEqual(deleted.storage_state, "deleted")
        self.assertIsNotNone(deleted.deleted_at)

    async def test_media_worker_role_is_narrow_and_non_login(self) -> None:
        async with session_factory() as db:
            can_login = await db.scalar(
                text("SELECT rolcanlogin FROM pg_roles WHERE rolname = :role"),
                {"role": MEDIA_WORKER_ROLE},
            )
            self.assertFalse(can_login)
            self.assertTrue(
                await db.scalar(
                    text("SELECT has_table_privilege(:role, 'repair_photo_evidence', 'SELECT')"),
                    {"role": MEDIA_WORKER_ROLE},
                )
            )
            self.assertFalse(
                await db.scalar(
                    text("SELECT has_table_privilege(:role, 'repair_photo_evidence', 'INSERT')"),
                    {"role": MEDIA_WORKER_ROLE},
                )
            )
            self.assertTrue(
                await db.scalar(
                    text(
                        "SELECT has_column_privilege(:role, 'repair_photo_evidence', "
                        "'storage_state', 'UPDATE')"
                    ),
                    {"role": MEDIA_WORKER_ROLE},
                )
            )
            self.assertFalse(
                await db.scalar(
                    text(
                        "SELECT has_column_privilege(:role, 'repair_photo_evidence', "
                        "'purpose', 'UPDATE')"
                    ),
                    {"role": MEDIA_WORKER_ROLE},
                )
            )

    def test_cron_reconciliation_fails_closed_without_exact_secret(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CRON_SECRET", None)
            self.assertFalse(cron_request_authorized(None))
            self.assertFalse(cron_request_authorized("Bearer anything"))
        with patch.dict(os.environ, {"CRON_SECRET": "photo-reconcile-secret"}):
            self.assertFalse(cron_request_authorized("Bearer wrong"))
            self.assertTrue(cron_request_authorized("Bearer photo-reconcile-secret"))


if __name__ == "__main__":
    unittest.main()
