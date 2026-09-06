from __future__ import annotations

import json
import re
from pathlib import Path

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v3 as v3
from . import identity_catalog_worker_v4 as v4
from . import identity_catalog_worker_v4_2 as v4_2

# V4.3 is a cache-only reconciliation pass over V4.2. It targets the residual
# package/page-presentation artifacts found in the V4.2 export without adding
# technical specifications or synthesizing missing trim rows.

_V4_2_NORMALIZE = v4._normalize_selection_label

_PURE_ENGINE_TOKEN_RE = re.compile(r"^(?:V-?[468]|I[346])$", re.I)
_PACKAGE_NUMBER_RE = re.compile(r"^\d+\s*(?:&|and|to|-)\s*\d+$", re.I)
_WHEEL_PRESENTATION_RE = re.compile(r"^wheels?\b", re.I)
_PACKAGE_MARKER_RE = re.compile(r"\b(?:Pkg|Pkgs|Package|Packages)\b", re.I)


def _normalize_package_grade(grade: str) -> str | None:
    """Normalize only package labels that consumer sources present as selections."""

    key = legacy.normalized_key(grade)

    # Honda marketed VP/Value Package as the same selection.
    if key == "value package":
        return "VP"

    # AcuraWatch Plus is an equipment/safety option rather than a trim grade.
    if re.fullmatch(r"AcuraWatch\s+Plus\s+(?:Pkg|Package)", grade, re.I):
        return None

    # Historical Tiburon pages expose numbered option bundles. They are not
    # separate trims; preserve the base grade and discard page-only bundle IDs.
    if re.fullmatch(r"Base\s+(?:Pkg|Package)\s+.+", grade, re.I):
        return "Base"
    if _PACKAGE_NUMBER_RE.fullmatch(grade):
        return None

    # Acura package taxonomy is marketed as the selectable grade on these pages.
    # Normalize source spelling so KBB and CarsDirect can reconcile.
    aliases: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"^Premium\s+(?:Pkg|Package)$", re.I), "Premium"),
        (
            re.compile(r"^Technology\s+Plus\s+(?:Pkg|Package)$", re.I),
            "Technology Plus",
        ),
        (
            re.compile(r"^(?:Tech|Technology)\s+(?:Pkg|Package)$", re.I),
            "Technology",
        ),
        (re.compile(r"^Advance\s+(?:Pkg|Package)$", re.I), "Advance"),
        (
            re.compile(
                r"^Premium\s*&\s*A-Spec\s+(?:Pkgs|Packages)$",
                re.I,
            ),
            "Premium A-Spec",
        ),
        (
            re.compile(
                r"^Technology\s+Plus\s*&\s*A-Spec\s+(?:Pkgs|Packages)$",
                re.I,
            ),
            "Technology Plus A-Spec",
        ),
        (
            re.compile(
                r"^(?:Tech|Technology)\s*&\s*A-Spec\s+(?:Pkgs|Packages)$",
                re.I,
            ),
            "Technology A-Spec",
        ),
        (
            re.compile(r"^Advance\s*&\s*Entertainment\s+(?:Pkgs|Packages)$", re.I),
            "Advance",
        ),
        (
            re.compile(
                r"^(?:Tech|Technology)\s*&\s*Entertainment\s+(?:Pkgs|Packages)$",
                re.I,
            ),
            "Technology",
        ),
    )
    for pattern, canonical in aliases:
        if pattern.fullmatch(grade):
            return canonical

    return grade


def _normalize_selection_label(
    label: str,
    family_label: str | None = None,
) -> str | None:
    body, grade = v3._split_body_prefix(label)
    grade = grade or label
    grade = legacy._SPACE_RE.sub(" ", grade).strip()

    if not grade:
        return None
    if family_label and legacy.normalized_key(grade) == legacy.normalized_key(family_label):
        return None
    if _PURE_ENGINE_TOKEN_RE.fullmatch(grade):
        return None
    if _WHEEL_PRESENTATION_RE.search(grade):
        return None

    # V4.2 already handles most leading w/... configuration text. Its export
    # exposed one remaining exact selection spelling.
    if re.fullmatch(r"w/\s*Technology", grade, re.I):
        grade = "Technology"

    grade = _normalize_package_grade(grade)
    if grade is None:
        return None

    normalized_input = v3._selection_label(grade, body)
    canonical = _V4_2_NORMALIZE(normalized_input, family_label)
    if canonical is None:
        return None

    # A trim row must add selection information beyond the model family itself.
    _body, canonical_grade = v3._split_body_prefix(canonical)
    canonical_grade = canonical_grade or canonical
    if family_label and legacy.normalized_key(canonical_grade) == legacy.normalized_key(
        family_label
    ):
        return None
    if _PURE_ENGINE_TOKEN_RE.fullmatch(canonical_grade):
        return None
    return canonical


async def export_json(path: str) -> None:
    await v4.export_json(path)
    destination = Path(path)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    scope = payload.setdefault("scope", {})
    scope["identity_label_strategy"] = "marketed_selection_v4_3"

    model_rows = payload.get("models", [])
    trims = [
        (model, trim)
        for model in model_rows
        if isinstance(model, dict)
        for trim in model.get("trims", [])
        if isinstance(trim, dict)
    ]
    quality = payload.setdefault("quality_summary", {})
    quality["residual_package_marker_rows"] = sum(
        1 for _model, trim in trims if _PACKAGE_MARKER_RE.search(str(trim.get("trim", "")))
    )
    quality["residual_engine_only_rows"] = sum(
        1
        for _model, trim in trims
        if _PURE_ENGINE_TOKEN_RE.fullmatch(str(trim.get("trim", "")).strip())
    )
    quality["residual_model_echo_rows"] = sum(
        1
        for model, trim in trims
        if legacy.normalized_key(str(trim.get("trim", "")))
        == legacy.normalized_key(str(model.get("model", "")))
    )
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=False),
        encoding="utf-8",
    )


def install_v4_3_behavior() -> None:
    v4_2.install_v4_2_behavior()
    v4._normalize_selection_label = _normalize_selection_label
    legacy.export_json = export_json


def main() -> None:
    install_v4_3_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
