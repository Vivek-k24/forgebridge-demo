import asyncio
from types import SimpleNamespace
from uuid import UUID

from partgraph.repair_experience.memory import storage

PNG = b"\x89PNG\r\n\x1a\n" + b"partgraph-photo"
TOKEN = "vercel_blob_rw_store123_secret"
PHOTO_ID = UUID("12345678-1234-5678-1234-567812345678")


def _configure_root(monkeypatch, tmp_path) -> str:
    monkeypatch.setattr(storage, "settings", SimpleNamespace(media_root=str(tmp_path)))
    return storage.new_storage_key(PHOTO_ID, "png")


def test_hosted_store_writes_private_blob_and_transient_cache(monkeypatch, tmp_path) -> None:
    storage_key = _configure_root(monkeypatch, tmp_path)
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", TOKEN)
    uploaded: list[tuple[str, bytes, str]] = []
    monkeypatch.setattr(
        storage,
        "_blob_put",
        lambda key, data, token: uploaded.append((key, data, token)),
    )

    path = asyncio.run(storage.store_photo(storage_key, PNG))

    assert uploaded == [(storage_key, PNG, TOKEN)]
    assert path.read_bytes() == PNG


def test_hosted_read_rehydrates_missing_transient_cache(monkeypatch, tmp_path) -> None:
    storage_key = _configure_root(monkeypatch, tmp_path)
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", TOKEN)
    monkeypatch.setattr(storage, "_blob_get", lambda key, token: PNG)

    path = storage.photo_path(storage_key)

    assert path.read_bytes() == PNG


def test_hosted_delete_removes_blob_and_transient_cache(monkeypatch, tmp_path) -> None:
    storage_key = _configure_root(monkeypatch, tmp_path)
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", TOKEN)
    path = tmp_path / storage_key
    path.write_bytes(PNG)
    deleted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        storage,
        "_blob_delete",
        lambda key, token: deleted.append((key, token)),
    )

    asyncio.run(storage.delete_photo_file(storage_key))

    assert deleted == [(storage_key, TOKEN)]
    assert not path.exists()


def test_local_storage_remains_default_without_blob_credentials(monkeypatch, tmp_path) -> None:
    storage_key = _configure_root(monkeypatch, tmp_path)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setattr(
        storage,
        "_blob_put",
        lambda *args: (_ for _ in ()).throw(AssertionError("Blob must not be called locally")),
    )

    path = asyncio.run(storage.store_photo(storage_key, PNG))

    assert path.read_bytes() == PNG
    assert storage.photo_path(storage_key) == path
