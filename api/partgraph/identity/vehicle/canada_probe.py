from __future__ import annotations

import csv
from io import StringIO
from urllib.request import Request, urlopen

CATALOG_URLS = (
    "https://open.canada.ca/data/dataset/98f1a129-f628-4ce4-b24d-6f16bf24dd64/"
    "resource/42495676-28b7-40f3-b0e0-3d7fe005ca56/download/"
    "my1995-2014-fuel-consumption-ratings-5-cycle.csv",
    "https://open.canada.ca/data/dataset/98f1a129-f628-4ce4-b24d-6f16bf24dd64/"
    "resource/9df1b18d-d036-4783-a61c-99f1f75b3ac5/download/"
    "my2026-fuel-consumption-ratings.csv",
    "https://open.canada.ca/data/dataset/98f1a129-f628-4ce4-b24d-6f16bf24dd64/"
    "resource/026e45b4-eb63-451f-b34f-d9308ea3a3d9/download/"
    "my2012-2026-battery-electric-vehicles.csv",
    "https://open.canada.ca/data/dataset/98f1a129-f628-4ce4-b24d-6f16bf24dd64/"
    "resource/8812228b-a6aa-4303-b3d0-66489225120d/download/"
    "my2012-2026-plug-in-hybrid-electric-vehicles.csv",
)


def _rows(url: str) -> list[dict[str, str]]:
    request = Request(url, headers={"Accept": "text/csv", "User-Agent": "PartGraph/0.9"})
    with urlopen(request, timeout=10.0) as response:
        body = response.read(3 * 1024 * 1024)
    text = body.decode("utf-8-sig")
    return list(csv.DictReader(StringIO(text)))


if __name__ == "__main__":
    print("PARTGRAPH_NRCAN_MODEL_PROBE_START")
    for url in CATALOG_URLS:
        rows = _rows(url)
        print(f"FILE {url.rsplit('/', 1)[-1]}")
        print(f"HEADERS {list(rows[0].keys()) if rows else []}")
        matches = [
            row
            for row in rows
            if (
                (row.get("Model year") == "2009" and row.get("Make") == "ACURA")
                or (row.get("Model year") == "2008" and row.get("Make") == "VOLKSWAGEN")
                or (row.get("Model year") == "2026" and row.get("Make") == "TOYOTA")
            )
        ]
        print(f"MATCHES {matches[:30]}")
    print("PARTGRAPH_NRCAN_MODEL_PROBE_END")
