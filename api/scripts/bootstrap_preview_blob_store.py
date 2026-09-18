from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.vercel.com/storage/stores/blob"
STORE_NAME = "partgraph-preview-private-media"


def main() -> None:
    if os.getenv("VERCEL_ENV", "").strip().casefold() != "preview":
        print("Preview Blob bootstrap skipped outside Vercel preview.")
        return

    if os.getenv("BLOB_STORE_ID", "").strip() or os.getenv(
        "BLOB_READ_WRITE_TOKEN", ""
    ).strip():
        print("Preview Blob bootstrap skipped: storage is already connected.")
        return

    token = os.getenv("VERCEL_OIDC_TOKEN", "").strip()
    project_id = os.getenv("VERCEL_PROJECT_ID", "").strip()
    if not token or not project_id:
        raise RuntimeError(
            "Preview Blob bootstrap requires VERCEL_OIDC_TOKEN and VERCEL_PROJECT_ID."
        )

    payload = json.dumps(
        {
            "name": STORE_NAME,
            "region": "iad1",
            "access": "private",
            "projectId": project_id,
        }
    ).encode("utf-8")
    request = Request(
        API_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(
            f"Preview Blob bootstrap was rejected by Vercel (HTTP {exc.code})."
        ) from exc
    except URLError as exc:
        raise RuntimeError("Preview Blob bootstrap could not reach Vercel.") from exc

    store = body.get("store") if isinstance(body, dict) else None
    store_id = store.get("id") if isinstance(store, dict) else None
    if not store_id:
        raise RuntimeError("Vercel created no identifiable Preview Blob store.")

    # Vercel injects storage bindings into new deployments, not the build that
    # created the resource. Failing here guarantees we never mistake this build
    # for the hosted durability proof. The next clean deployment must receive
    # BLOB_STORE_ID and pass verify_hosted_photo_persistence.py normally.
    raise RuntimeError(
        "Preview private Blob store was created successfully; "
        "a fresh deployment is required before durability can be proven."
    )


if __name__ == "__main__":
    main()
