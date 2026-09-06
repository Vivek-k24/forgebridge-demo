from __future__ import annotations

import json
from pathlib import Path

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v4_4 as v4_4

# V4.5 closes the remaining exact random-sample artifacts found after the V4.4
# coverage pass. These are source-backed identity corrections only. No technical
# vehicle specifications are introduced.

_FINAL_SAMPLE_SUPPLEMENTS = {
    (
        "Lexus",
        2019,
        "ES",
    ): (
        "lexus_official",
        (
            (
                "350",
                "https://www.lexus.com/content/dam/lexus/documents/brochures/models/2019/MY19-Lexus-ES-and-ES-Hybrid-Brochure.pdf",
            ),
            (
                "300h",
                "https://www.lexus.com/content/dam/lexus/documents/brochures/models/2019/MY19-Lexus-ES-and-ES-Hybrid-Brochure.pdf",
            ),
            (
                "350 F Sport",
                "https://www.lexus.com/content/dam/lexus/documents/brochures/models/2019/MY19-Lexus-ES-and-ES-Hybrid-Brochure.pdf",
            ),
        ),
    ),
    (
        "Lexus",
        2019,
        "LC",
    ): (
        "lexus_official",
        (
            (
                "500",
                "https://www.lexus.com/content/dam/lexus/documents/brochures/models/2019/MY19-Lexus-LC-LCh-Brochure.pdf",
            ),
            (
                "500h",
                "https://www.lexus.com/content/dam/lexus/documents/brochures/models/2019/MY19-Lexus-LC-LCh-Brochure.pdf",
            ),
        ),
    ),
    (
        "Subaru",
        2012,
        "Legacy",
    ): (
        "edmunds_reference",
        (
            (
                "2.5GT Limited",
                "https://www.edmunds.com/subaru/legacy/2012/review/",
            ),
        ),
    ),
}

_FINAL_SAMPLE_REPLACEMENTS = {
    # The 2019 ES brochure presents Premium as a package; Luxury, Ultra Luxury,
    # F SPORT, ES 350 and ES 300h remain marketed selections.
    ("Lexus", 2019, "ES"): {"300h Premium", "350 Premium"},
    # LC 500 and LC 500h are the marketed identities. A separate LC "Base" row
    # is a consumer-page presentation artifact.
    ("Lexus", 2019, "LC"): {"Base"},
    # 2012 Legacy's turbo grade was 2.5GT Limited, not a separate 2.5GT grade.
    ("Subaru", 2012, "Legacy"): {"2.5GT"},
}


async def export_json(path: str) -> None:
    await v4_4.export_json(path)
    destination = Path(path)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload.setdefault("scope", {})["identity_label_strategy"] = "marketed_selection_v4_5"
    payload.setdefault("quality_summary", {})["final_random_sample_cleanup"] = True
    destination.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")


def install_v4_5_behavior() -> None:
    v4_4._SOURCE_BACKED_SUPPLEMENTS.update(_FINAL_SAMPLE_SUPPLEMENTS)
    v4_4._REPLACED_LABELS.update(_FINAL_SAMPLE_REPLACEMENTS)
    v4_4.install_v4_4_behavior()
    legacy.export_json = export_json


def main() -> None:
    install_v4_5_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
