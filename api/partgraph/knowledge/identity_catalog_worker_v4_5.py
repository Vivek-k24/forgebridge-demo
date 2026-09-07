from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v3 as v3
from . import identity_catalog_worker_v4 as v4
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
_V4_3_NORMALIZE_SELECTION_LABEL = v4_3._normalize_selection_label
_ACURAWATCH_PLUS_SUFFIX_RE = re.compile(
    r"^(.+?)\s*&\s*AcuraWatch\s+Plus\s+(?:Pkg|Package)$",
    re.I,
)
_TRAILING_LIFTBACK_RE = re.compile(r"\s+Liftback$", re.I)
_TRAILING_SPORT_RE = re.compile(r"(?:^|\s)Sport$", re.I)


def _normalize_package_grade(grade: str) -> str | None:
    """Drop AcuraWatch Plus equipment suffixes without losing the real grade."""

    match = _ACURAWATCH_PLUS_SUFFIX_RE.fullmatch(grade.strip())
    if match:
        return _V4_3_NORMALIZE_PACKAGE_GRADE(match.group(1).strip())
    return _V4_3_NORMALIZE_PACKAGE_GRADE(grade)


def _normalize_selection_label(
    label: str,
    family_label: str | None = None,
) -> str | None:
    """Remove residual KBB body-presentation wording from canonical identity."""

    canonical = _V4_3_NORMALIZE_SELECTION_LABEL(label, family_label)
    if canonical is None:
        return None

    body, grade = v3._split_body_prefix(canonical)
    grade = grade or canonical
    if legacy.normalized_key(grade) == "liftback":
        grade = "Base"
    else:
        grade = _TRAILING_LIFTBACK_RE.sub("", grade).strip()

    if not grade:
        grade = "Base"
    return v3._selection_label(grade, body)


def _strip_trailing_sport(grade: str) -> str:
    if legacy.normalized_key(grade) == "sport":
        return "Base"
    return re.sub(r"\s+Sport$", "", grade, flags=re.I).strip()


def _collapse_kbb_body_presentation_sport(
    finalized: dict[str, dict[str, tuple[str, dict[str, object]]]],
) -> dict[str, dict[str, tuple[str, dict[str, object]]]]:
    """Collapse historical KBB `... Sport <body>` presentation conservatively.

    KBB uses `Sport Wagon 4D` / `Sport Coupe 2D` as a body-style presentation on
    a number of older pages. `Sport` can also be a genuine modern trim, so it is
    removed only when every KBB-observed row for that exact body presentation
    ends in Sport and the shorter grade is independently visible elsewhere in
    the same model-year observation set. Genuine `Outback Sport` is retained.
    """

    result = {key: dict(provider_map) for key, provider_map in finalized.items()}
    parsed: dict[str, tuple[str | None, str]] = {}
    body_groups: dict[str, list[str]] = defaultdict(list)
    grade_keys: dict[str, set[str]] = defaultdict(set)

    for key, provider_map in finalized.items():
        labels = [label for label, _evidence in provider_map.values()]
        if not labels:
            continue
        label = min(labels, key=lambda value: (len(value), value.casefold()))
        body, grade = v3._split_body_prefix(label)
        grade = grade or label
        parsed[key] = (body, grade)
        grade_keys[legacy.normalized_key(grade)].add(key)
        # Include corroborated KBB rows in the body-group context so a genuine
        # non-Sport grade cannot be hidden merely because another provider also
        # observed it. Rewrites themselves remain KBB-only below.
        if body is not None and "kbb" in provider_map:
            body_groups[body].append(key)

    rewrites: list[tuple[str, str, str]] = []
    for body, keys in body_groups.items():
        if not keys:
            continue
        if not all(_TRAILING_SPORT_RE.search(parsed[key][1]) for key in keys):
            continue

        for key in keys:
            provider_map = finalized[key]
            if set(provider_map) != {"kbb"}:
                continue
            _body, grade = parsed[key]
            if legacy.normalized_key(grade) == "outback sport":
                continue
            shorter = _strip_trailing_sport(grade)
            shorter_key = legacy.normalized_key(shorter)
            support = grade_keys.get(shorter_key, set()) - {key}
            if not support:
                continue
            canonical = v3._selection_label(shorter, body)
            rewrites.append((key, legacy.normalized_key(canonical), canonical))

    for old_key, new_key, canonical in rewrites:
        provider_map = result.pop(old_key, None)
        if provider_map is None:
            continue
        target = result.setdefault(new_key, {})
        for provider, (_old_label, evidence) in provider_map.items():
            target[provider] = (canonical, evidence)

    return result


_FINAL_SAMPLE_SUPPLEMENTS = {
    (
        "Hyundai",
        2010,
        "Accent",
    ): (
        "edmunds_reference",
        (
            (
                "Hatchback Blue",
                "https://www.edmunds.com/hyundai/accent/2010/review/",
            ),
        ),
    ),
    (
        "Lexus",
        2010,
        "IS",
    ): (
        "edmunds_reference",
        (
            (
                "Sedan 250",
                "https://www.edmunds.com/lexus/is-250/2010/trims/",
            ),
            (
                "Sedan 350",
                "https://www.edmunds.com/lexus/is-350/2010/trims/",
            ),
            (
                "Convertible 250",
                "https://www.edmunds.com/lexus/is-250-c/2010/convertible/features-specs/",
            ),
            (
                "Convertible 350",
                "https://www.edmunds.com/lexus/is-350-c/2010/convertible/features-specs/",
            ),
        ),
    ),
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
        2006,
        "Impreza",
    ): (
        "edmunds_reference",
        (
            (
                "Wagon Outback Sport Special Edition",
                "https://www.edmunds.com/subaru/impreza/2006/review/",
            ),
        ),
    ),
    (
        "Subaru",
        2008,
        "Impreza",
    ): (
        "edmunds_reference",
        (
            (
                "Wagon WRX STI",
                "https://www.edmunds.com/subaru/impreza/2008/wrx-sti/features-specs/",
            ),
        ),
    ),
    (
        "Subaru",
        2010,
        "Impreza",
    ): (
        "edmunds_reference",
        (
            (
                "Wagon WRX STI",
                "https://www.edmunds.com/subaru/impreza/2010/trims/",
            ),
            (
                "Wagon WRX STI Special Edition",
                "https://www.edmunds.com/subaru/impreza/2010/wrx-sti-special-edition/features-specs/",
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
    # KBB's malformed historical body label is not part of the Accent trim.
    ("Hyundai", 2010, "Accent"): {"Hatchback Blue Hatchback D"},
    # KBB uses Sport before Sedan/Convertible as body presentation for these
    # 2010 IS styles; Edmunds identifies the underlying 250/350 selections.
    ("Lexus", 2010, "IS"): {
        "Convertible 250 Sport",
        "Convertible 350 Sport",
        "Sedan 250 Sport",
        "Sedan 350 Sport",
    },
    # The 2019 ES brochure presents Premium as a package; Luxury, Ultra Luxury,
    # F SPORT, ES 350 and ES 300h remain marketed selections.
    ("Lexus", 2019, "ES"): {"300h Premium", "350 Premium"},
    # LC 500 and LC 500h are the marketed identities. A separate LC "Base" row
    # is a consumer-page presentation artifact.
    ("Lexus", 2019, "LC"): {"Base"},
    # Historical KBB pages append Sport before Wagon as a body presentation.
    ("Subaru", 2006, "Impreza"): {"Wagon Outback Sport Special Edition Sport"},
    ("Subaru", 2008, "Impreza"): {"Wagon WRX STI Sport"},
    ("Subaru", 2010, "Impreza"): {
        "Wagon WRX STI Sport",
        "Wagon WRX STI Special Edition Sport",
    },
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

    # V4's finalizer resolves the selection normalizer dynamically. Install the
    # residual Liftback cleanup after V4.4 has installed the V4.3 stack.
    v4._normalize_selection_label = _normalize_selection_label

    # Wrap the fully installed finalizer, then expose the wrapper to both V3 and
    # V4 because V4.2's collector resolves V3's finalizer dynamically.
    base_finalize = v3._finalize_trim_observations

    def finalize_with_v4_5_cleanup(
        observations: dict[str, dict[str, tuple[str, dict[str, object]]]],
        provider_labels: dict[str, list[str]],
    ) -> dict[str, dict[str, tuple[str, dict[str, object]]]]:
        finalized = base_finalize(observations, provider_labels)
        return _collapse_kbb_body_presentation_sport(finalized)

    v3._finalize_trim_observations = finalize_with_v4_5_cleanup
    v4._finalize_trim_observations = finalize_with_v4_5_cleanup
    legacy.export_json = export_json


def main() -> None:
    install_v4_5_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
