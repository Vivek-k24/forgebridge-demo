from __future__ import annotations

import json
import re
from pathlib import Path

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v4_2 as v4_2
from . import identity_catalog_worker_v4_3 as v4_3
from . import identity_catalog_worker_v4_4 as v4_4

# V4.5 closes the remaining exact random-sample artifacts found after the V4.4
# coverage pass. These are source-backed identity corrections only. No technical
# vehicle specifications are introduced.

# V4.4 wraps the collector so it can add source-backed supplements after each
# make/year. Its original module-level base accidentally captured the older V3
# collector. Restore the V4.2 collector here before V4.4 installs its wrapper so
# the exact-year provenance/future-model safeguards remain active in V4.5.
_V4_2_COLLECT_MAKE_YEAR = v4_2._collect_make_year
_V4_3_NORMALIZE_PACKAGE_GRADE = v4_3._normalize_package_grade
_ACURAWATCH_PLUS_SUFFIX_RE = re.compile(
    r"^(.+?)\s*&\s*AcuraWatch\s+Plus\s+(?:Pkg|Package)$",
    re.I,
)


def _normalize_package_grade(grade: str) -> str | None:
    """Drop AcuraWatch Plus equipment suffixes without losing the real grade."""

    match = _ACURAWATCH_PLUS_SUFFIX_RE.fullmatch(grade.strip())
    if match:
        return _V4_3_NORMALIZE_PACKAGE_GRADE(match.group(1).strip())
    return _V4_3_NORMALIZE_PACKAGE_GRADE(grade)


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
    # Preserve V4.2's stricter collection boundary under the V4.4/V4.5
    # supplement wrapper. In particular, brand-new NHTSA-only 2027 names must
    # not enter the catalog without a prior accepted family.
    v4_4._BASE_COLLECT_MAKE_YEAR = _V4_2_COLLECT_MAKE_YEAR

    # V4.3 already normalizes the known package spellings. Extend that same
    # identity-only normalizer for the final combined AcuraWatch presentation.
    v4_3._normalize_package_grade = _normalize_package_grade

    v4_4._SOURCE_BACKED_SUPPLEMENTS.update(_FINAL_SAMPLE_SUPPLEMENTS)
    v4_4._REPLACED_LABELS.update(_FINAL_SAMPLE_REPLACEMENTS)
    v4_4.install_v4_4_behavior()
    legacy.export_json = export_json


def main() -> None:
    install_v4_5_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
