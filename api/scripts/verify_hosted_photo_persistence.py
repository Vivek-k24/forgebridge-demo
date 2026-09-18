from __future__ import annotations

import asyncio
import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image

from partgraph.repair_experience.memory import storage


def _probe_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), (20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


async def _run_probe() -> None:
    token = os.getenv("BLOB_READ_WRITE_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Preview durable-photo validation requires BLOB_READ_WRITE_TOKEN."
        )

    key = storage.new_storage_key(uuid4(), "png")
    expected = _probe_png()
    local_path: Path | None = None
    stored = False

    try:
        local_path = await storage.store_photo(key, expected)
        stored = True
        if local_path.read_bytes() != expected:
            raise RuntimeError("Hosted photo write changed the stored payload.")

        # Vercel function disk is transient. Removing the local cache forces the
        # next read through the private Blob backend and proves durable rehydration.
        local_path.unlink(missing_ok=True)
        rehydrated = storage.photo_path(key)
        if rehydrated.read_bytes() != expected:
            raise RuntimeError("Hosted photo rehydration returned different bytes.")

        await storage.delete_photo_file(key)
        stored = False
        if rehydrated.exists():
            raise RuntimeError("Hosted photo deletion left the transient cache behind.")
    finally:
        if stored:
            try:
                await storage.delete_photo_file(key)
            except Exception:
                pass
        if local_path is not None:
            local_path.unlink(missing_ok=True)


def main() -> None:
    if os.getenv("VERCEL_ENV", "").strip().casefold() != "preview":
        print("Hosted photo persistence probe skipped outside Vercel preview.")
        return

    asyncio.run(_run_probe())
    print(
        "Hosted photo persistence probe passed: private Blob write, "
        "cache-loss rehydration, and delete all succeeded."
    )


if __name__ == "__main__":
    main()
