import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from partgraph.repair_experience.memory import storage

PNG = b"\x89PNG\r\n\x1a\n" + b"partgraph-photo"
TOKEN = "vercel_blob_rw_store123_secret"
PHOTO_ID = UUID("12345678-1234-5678-1234-567812345678")


class HostedPhotoStorageTests(unittest.TestCase):
    def _settings(self, root: str):
        return patch.object(storage, "settings", SimpleNamespace(media_root=root))

    def test_hosted_store_writes_private_blob_and_transient_cache(self) -> None:
        with tempfile.TemporaryDirectory() as root, self._settings(root):
            storage_key = storage.new_storage_key(PHOTO_ID, "png")
            uploaded: list[tuple[str, bytes, str]] = []
            with (
                patch.dict("os.environ", {"BLOB_READ_WRITE_TOKEN": TOKEN}),
                patch.object(
                    storage,
                    "_blob_put",
                    side_effect=lambda key, data, token: uploaded.append(
                        (key, data, token)
                    ),
                ),
            ):
                path = asyncio.run(storage.store_photo(storage_key, PNG))

            self.assertEqual(uploaded, [(storage_key, PNG, TOKEN)])
            self.assertEqual(path.read_bytes(), PNG)

    def test_hosted_read_rehydrates_missing_transient_cache(self) -> None:
        with tempfile.TemporaryDirectory() as root, self._settings(root):
            storage_key = storage.new_storage_key(PHOTO_ID, "png")
            with (
                patch.dict("os.environ", {"BLOB_READ_WRITE_TOKEN": TOKEN}),
                patch.object(storage, "_blob_get", return_value=PNG),
            ):
                path = storage.photo_path(storage_key)

            self.assertEqual(path.read_bytes(), PNG)

    def test_hosted_delete_removes_blob_and_transient_cache(self) -> None:
        with tempfile.TemporaryDirectory() as root, self._settings(root):
            storage_key = storage.new_storage_key(PHOTO_ID, "png")
            path = Path(root) / storage_key
            path.write_bytes(PNG)
            deleted: list[tuple[str, str]] = []
            with (
                patch.dict("os.environ", {"BLOB_READ_WRITE_TOKEN": TOKEN}),
                patch.object(
                    storage,
                    "_blob_delete",
                    side_effect=lambda key, token: deleted.append((key, token)),
                ),
            ):
                asyncio.run(storage.delete_photo_file(storage_key))

            self.assertEqual(deleted, [(storage_key, TOKEN)])
            self.assertFalse(path.exists())

    def test_oidc_credentials_are_used_when_blob_store_is_connected(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BLOB_READ_WRITE_TOKEN": "",
                "VERCEL_OIDC_TOKEN": "oidc-fixture-token",
                "BLOB_STORE_ID": "store_store123",
            },
            clear=False,
        ):
            self.assertEqual(storage._blob_token(), "oidc-fixture-token")
            self.assertEqual(storage._blob_store_id("oidc-fixture-token"), "store123")

    def test_local_storage_remains_default_without_blob_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as root, self._settings(root):
            storage_key = storage.new_storage_key(PHOTO_ID, "png")
            with (
                patch.dict("os.environ", {}, clear=False),
                patch.object(
                    storage,
                    "_blob_put",
                    side_effect=AssertionError("Blob must not be called locally"),
                ),
            ):
                import os

                os.environ.pop("BLOB_READ_WRITE_TOKEN", None)
                path = asyncio.run(storage.store_photo(storage_key, PNG))
                self.assertEqual(path.read_bytes(), PNG)
                self.assertEqual(storage.photo_path(storage_key), path)


if __name__ == "__main__":
    unittest.main()
