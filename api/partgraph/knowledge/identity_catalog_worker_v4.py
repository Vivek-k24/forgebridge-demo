from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v2 as v2
from . import identity_catalog_worker_v3 as v3

# V4.2 is a cache-reconciliation pass over V3. It does not add technical specs.
# It fixes source-presentation artifacts exposed by the September 6 catalog audits.

_V2_CANONICALIZE = v2.canonicalize_model_inventory
_V3_MODEL_VARIANTS = v3.model_variants
_V3_FINALIZE = v3._finalize_trim_observations
_V3_STRICT_TRIM = v3._strict_trim_value
_ORIGINAL_COMBINE = legacy.combine_trim_variant

_BODY_PREFIX_KEYS_V4 = {
    "sport utility": "SUV",
    "suv": "SUV",
    "minivan": "Van",
    "van": "Van",
    "hatchback": "Hatchback",
    "convertible": "Convertible",
    "roadster": "Roadster",
    "sedan": "Sedan",
    "coupe": "Coupe",
    "wagon": "Wagon",
    "pickup": "Pickup",
}

_SPECIAL_VARIANTS = {
    "si": "Si",
    "type r": "Type R",
    "type s": "Type S",
    "a spec": "A-Spec",
}
_MODEL_PAGE_VARIANTS = {
    "hybrid",
    "si",
    "type r",
    "type s",
    "e fcev",
}
_STANDALONE_PACKAGE_KEYS = {
    "2 tone",
    "two tone",
    "tow",
    "towing",
    "tow hitch",
}
_CONFIG_MARKER_RE = re.compile(
    r"(?:\bw/|\bw/o\b|\b\d+\s+passenger\b|auto access seat|"
    r"\bpackage\b|\bpkg\b|navigation|nav system|honda sensing|"
    r"\bautomatic\b|\bmanual\b|\bcvt\b|\bdct\b|\b50 state\b|"
    r"\binterior\b|\bleather\b|blind spot information|solar roof)",
    re.I,
)
_TRAILING_OPTION_RE = re.compile(r"\s+w/.*$", re.I)
_PASSENGER_RE = re.compile(
    r"\s+(?:7|8)\s+Passenger(?:\s+Auto Access Seat)?$",
    re.I,
)
_AUTO_ACCESS_RE = re.compile(r"\s+Auto Access Seat$", re.I)
_LEADING_TRANSMISSION_RE = re.compile(
    r"^w/\s*(?:"
    r"(?:4|5|6|7|8|9|10)[- ]?(?:Speed|Spd)\s+(?:Automatic|Auto|Manual)|"
    r"Automatic|Manual|CVT|DCT"
    r")[/ ]*",
    re.I,
)
_DRIVETRAIN_TOKEN_RE = re.compile(
    r"(?:(?<=^)|(?<=\s))(?:SH-AWD|AWD|FWD|RWD|4WD|2WD|4X4|4X2)(?=\s|$)",
    re.I,
)
_YEAR_PREFIXED_LABEL_RE = re.compile(r"^(?:19|20)\d{2}\s+[A-Za-z]", re.I)
_TRANSMISSION_ONLY_RE = re.compile(
    r"^(?:Continuously Variable Transmission|CVT|DCT|Automatic|Manual|"
    r"Automatic Transmission|Manual Transmission|"
    r"(?:4|5|6|7|8|9|10)[- ]?(?:Speed|Spd)\s+(?:Automatic|Auto|Manual))$",
    re.I,
)
_NON_TRIM_SELECTION_RE = re.compile(
    r"(?:blind spot information|solar roof|^wheels?$|hawaii only)",
    re.I,
)
_LEADING_ENGINE_RE = re.compile(
    r"^(?:\d+\.\d+(?:L|T)?|V-?[468]|I[346])\s+",
    re.I,
)
_TRAILING_ENGINE_RE = re.compile(r"\s+(?:V-?[468]|I[346])$", re.I)
_TRAILING_TRANSMISSION_RE = re.compile(
    r"(?:\s+(?:V-?[468]|I[346]))?\s+"
    r"(?:4|5|6|7|8|9|10)[- ]?(?:Speed|Spd)\s+"
    r"(?:Automatic|Auto|Manual)$",
    re.I,
)
_PURE_NUMERIC_GRADE_RE = re.compile(r"^\d+(?:\.\d+)?(?:L|T)?$", re.I)
_PURE_ENGINE_GRADE_RE = re.compile(r"^\d+\.\d+(?:L|T)$", re.I)


def _provider_labels_have_hybrid(provider_labels: dict[str, list[str]]) -> bool:
    return any(
        re.search(r"\b(?:hybrid|hev)\b", label, re.I)
        for labels in provider_labels.values()
        for label in labels
    )


def canonicalize_model_inventory(
    nhtsa_models: list[str],
    fueleconomy_models: list[str],
    *,
    make: str | None = None,
    year: int | None = None,
) -> dict[str, dict[str, list[str]]]:
    # V4.1 remembered hybrid capability globally by make/model. That allowed a
    # hybrid observed in one model year to create a synthetic "{model} Hybrid"
    # consumer-page alias in unrelated years. Hybrid aliases must be exact-year
    # evidence only, so canonicalization is deliberately stateless here.
    return _V2_CANONICALIZE(
        nhtsa_models,
        fueleconomy_models,
        make=make,
        year=year,
    )


def _simple_variant(fragment: str) -> str | None:
    tokens = [
        token
        for token in v2._components(fragment)
        if token not in v2._DRIVETRAIN_SUFFIX_TOKENS
        and token not in {"hybrid", "hev"}
    ]
    key = " ".join(tokens)
    aliases = {
        "sport": "Sport",
        "touring": "Touring",
        "elite": "Elite",
        "black": "Black Edition",
        "black edition": "Black Edition",
    }
    return aliases.get(key)


def model_variants(canonical_model: str, source_model: str) -> tuple[str, ...]:
    remainder = v3._remove_model_family(canonical_model, source_model)
    hybrid_context = bool(re.search(r"\b(?:hybrid|hev)\b", remainder, re.I))
    if hybrid_context and "/" in remainder:
        variants: list[str] = []
        for part in remainder.split("/"):
            variant = _simple_variant(part)
            if variant is not None:
                variants.append(f"{variant} Hybrid")
        if variants:
            return tuple(dict.fromkeys(variants))
        return ("Hybrid",)
    return _V3_MODEL_VARIANTS(canonical_model, source_model)


def model_variant(canonical_model: str, source_model: str) -> str | None:
    variants = model_variants(canonical_model, source_model)
    return variants[0] if variants else None


def _source_model_aliases(
    canonical_model: str,
    provider_labels: dict[str, list[str]],
) -> list[str]:
    aliases = [canonical_model]
    for labels in provider_labels.values():
        for source_model in labels:
            for variant in model_variants(canonical_model, source_model):
                key = legacy.normalized_key(variant)
                if key in _MODEL_PAGE_VARIANTS:
                    aliases.append(f"{canonical_model} {variant}")

    # Simplified Hybrid pages are useful when an exact-year NHTSA/FuelEconomy
    # label proves that this model-year has a hybrid configuration. Never carry
    # this alias forward from a different year.
    if _provider_labels_have_hybrid(provider_labels):
        aliases.append(f"{canonical_model} Hybrid")

    return sorted(
        dict.fromkeys(aliases),
        key=lambda value: (value != canonical_model, value.casefold()),
    )


def combine_trim_variant(trim: str | None, variant: str | None) -> str | None:
    if trim is None or variant is None:
        return _ORIGINAL_COMBINE(trim, variant)

    _body_style, grade = v3._split_body_prefix(trim)
    grade_key = legacy.normalized_key(grade)
    variant_key = legacy.normalized_key(variant)
    if grade_key in {"base", "standard"} and variant_key in _SPECIAL_VARIANTS:
        return _SPECIAL_VARIANTS[variant_key]
    return _ORIGINAL_COMBINE(trim, variant)


def _strict_trim_value(value: str | None) -> str | None:
    cleaned = _V3_STRICT_TRIM(value)
    if cleaned is None:
        return None
    if legacy.normalized_key(cleaned) in _STANDALONE_PACKAGE_KEYS:
        return None
    return cleaned


def _canonical_family_label(provider_labels: dict[str, list[str]]) -> str | None:
    """Infer the canonical family prefix already represented by the model row."""

    labels = list(provider_labels.get("nhtsa_vpic", []))
    if not labels:
        labels = [
            label
            for provider_values in provider_labels.values()
            for label in provider_values
        ]
    if not labels:
        return None

    return min(
        labels,
        key=lambda value: (
            len(v2._components(value)),
            len(value),
            value.casefold(),
        ),
    )


def _strip_family_prefix(value: str, family_label: str | None) -> str:
    if not family_label:
        return value
    prefix = f"{family_label} "
    if value.casefold().startswith(prefix.casefold()):
        return value[len(prefix) :].strip()
    return value


def _strip_drivetrain(value: str) -> tuple[str, bool]:
    cleaned = _DRIVETRAIN_TOKEN_RE.sub(" ", value)
    cleaned = legacy._SPACE_RE.sub(" ", cleaned).strip()
    return cleaned, cleaned != value


def _package_selection(option: str) -> str | None:
    cleaned = re.sub(r"\b(?:Pkgs?|Packages?)\b", " ", option, flags=re.I)
    cleaned = re.sub(r"\bTech\b", "Technology", cleaned, flags=re.I)
    cleaned = re.sub(r"\bAdvanced\b", "Advance", cleaned, flags=re.I)
    cleaned = re.sub(r"\bEntertainment\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\bAuto Trans\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\band\b|&", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+\d+(?:\.\d+)?(?:L|T)?$", "", cleaned, flags=re.I)
    cleaned = legacy._SPACE_RE.sub(" ", cleaned).strip()
    key = legacy.normalized_key(cleaned)

    has_aspec = "a spec" in key
    has_advance = "advance" in key
    has_technology = "technology" in key
    if has_aspec and has_advance:
        return "A-Spec Advance"
    if has_aspec:
        return "A-Spec"
    if has_advance:
        return "Advance"
    if has_technology:
        return "Technology"
    return None


def _normalize_leading_with_configuration(grade: str) -> str | None:
    """Recover the marketed grade from source strings that begin with w/..."""

    if re.match(r"^w/\s*(?:Automatic//)?(?:Tech|Technology)\s+Pkg\b", grade, re.I):
        return "Technology"
    if re.match(r"^w/\s*Advance\s+Pkg\b", grade, re.I):
        return "Advance"
    if re.match(r"^w/\s*Navigation\s+", grade, re.I):
        return re.sub(r"^w/\s*Navigation\s+", "", grade, flags=re.I).strip()

    stripped = _LEADING_TRANSMISSION_RE.sub("", grade).strip()
    if stripped != grade:
        stripped = _LEADING_ENGINE_RE.sub("", stripped).strip()
        return stripped or None

    if grade.casefold().startswith("w/"):
        return None
    return grade


def _normalize_special_grade(grade: str) -> tuple[str, bool]:
    """Return normalized marketed grade and whether body style should be dropped."""

    grade = re.sub(r"\bType-R\b", "Type R", grade, flags=re.I)
    grade = re.sub(r"\bA-SPEC\b", "A-Spec", grade, flags=re.I)
    key = legacy.normalized_key(grade)

    aliases = {
        "si base": ("Si", True),
        "si summer tires": ("Si", True),
        "n base": ("N", True),
        "type r": ("Type R", True),
        "type r sport": ("Type R", True),
        "type r touring": ("Type R", True),
        "touring type r": ("Type R", True),
        "type s sport cpe": ("Type S", True),
        "type r limited edition": ("Type R Limited Edition", False),
        "limited edition type r": ("Type R Limited Edition", False),
    }
    if key in aliases:
        return aliases[key]

    grade = re.sub(r"^Base\s+Hybrid$", "Hybrid", grade, flags=re.I)
    grade = re.sub(r"\s+Hybrid\s+Base$", " Hybrid", grade, flags=re.I)
    grade = re.sub(r"^Hybrid\s+Base$", "Hybrid", grade, flags=re.I)

    hybrid_prefix = re.match(r"^Hybrid\s+(.+)$", grade, re.I)
    if hybrid_prefix:
        remainder = hybrid_prefix.group(1).strip()
        if remainder and legacy.normalized_key(remainder) != "base":
            grade = f"{remainder} Hybrid"

    key = legacy.normalized_key(grade)
    return grade, key in {"si", "n", "type r", "type s", "a spec"}


def _normalize_selection_label(
    label: str,
    family_label: str | None = None,
) -> str | None:
    body, grade = v3._split_body_prefix(label)
    grade = grade or label
    grade = _strip_family_prefix(grade, family_label).strip()
    key = legacy.normalized_key(grade)

    if not grade or key in _STANDALONE_PACKAGE_KEYS:
        return None
    if _YEAR_PREFIXED_LABEL_RE.search(grade):
        return None
    if _NON_TRIM_SELECTION_RE.search(grade):
        return None
    if _TRANSMISSION_ONLY_RE.fullmatch(grade):
        return None

    if key.startswith("base "):
        suffix = key[len("base ") :]
        if suffix in _SPECIAL_VARIANTS:
            return _SPECIAL_VARIANTS[suffix]

    leading = _normalize_leading_with_configuration(grade)
    if leading is None:
        return None
    grade = leading

    # Acura and several historical consumer catalogs encode marketed selection
    # packages after drivetrain/base text. Keep the marketed package grade while
    # dropping drivetrain and non-selection entertainment/navigation qualifiers.
    with_match = re.match(r"^(.*?)\s+w/(.+)$", grade, re.I)
    if with_match:
        prefix = with_match.group(1).strip()
        option = with_match.group(2).strip()
        prefix, _ = _strip_drivetrain(prefix)
        if legacy.normalized_key(prefix) in {"base", "standard"}:
            prefix = ""

        package = _package_selection(option)
        if package is not None:
            prefix_key = legacy.normalized_key(prefix)
            if prefix_key == "type s":
                grade = "Type S Advance" if "advance" in legacy.normalized_key(package) else "Type S"
            elif not prefix:
                grade = package
            else:
                # A real grade plus an optional package remains the real grade.
                grade = prefix
        else:
            # Navigation/seating/transmission/etc. are configuration qualifiers.
            grade = prefix

    grade = _PASSENGER_RE.sub("", grade).strip()
    grade = _AUTO_ACCESS_RE.sub("", grade).strip()

    grade, drivetrain_removed = _strip_drivetrain(grade)
    if not grade:
        return None

    # Normalize package spelling when the package itself is the marketed grade.
    grade = re.sub(
        r"\bA-Spec\s+(?:Tech|Technology)\s+(?:Pkg|Package)\b",
        "A-Spec Technology",
        grade,
        flags=re.I,
    )
    grade = re.sub(
        r"\bA-Spec\s+(?:Pkg|Package)\b",
        "A-Spec",
        grade,
        flags=re.I,
    )
    grade = re.sub(
        r"\b(?:Tech|Technology)\s+(?:Pkg|Package)\b",
        "Technology",
        grade,
        flags=re.I,
    )
    grade = re.sub(
        r"\bAdvance\s+(?:Pkg|Package)\b",
        "Advance",
        grade,
        flags=re.I,
    )

    # Engine/transmission/drivetrain are separate identity facts, not trim.
    grade = _LEADING_ENGINE_RE.sub("", grade).strip()
    grade = _TRAILING_TRANSMISSION_RE.sub("", grade).strip()
    grade = _TRAILING_ENGINE_RE.sub("", grade).strip()
    if not grade or _TRANSMISSION_ONLY_RE.fullmatch(grade):
        return None
    if _PURE_ENGINE_GRADE_RE.fullmatch(grade):
        return None
    if drivetrain_removed and _PURE_NUMERIC_GRADE_RE.fullmatch(grade):
        return None

    # Preserve the marketed grade spelling used by the accepted Honda fixture.
    grade = re.sub(r"\bSport L\b", "Sport-L", grade, flags=re.I)

    grade, drop_body = _normalize_special_grade(grade)
    if drop_body:
        body = None

    if not grade:
        return None
    if legacy.normalized_key(grade) in _STANDALONE_PACKAGE_KEYS:
        return None

    return v3._selection_label(grade, body)


def _label_has_config_marker(label: str) -> bool:
    return bool(_CONFIG_MARKER_RE.search(label))


def _finalize_trim_observations(
    observations: dict[str, dict[str, tuple[str, dict[str, object]]]],
    provider_labels: dict[str, list[str]],
) -> dict[str, dict[str, tuple[str, dict[str, object]]]]:
    base = _V3_FINALIZE(observations, provider_labels)
    family_label = _canonical_family_label(provider_labels)

    normalized: dict[str, dict[str, tuple[str, dict[str, object]]]] = defaultdict(dict)
    for provider_map in base.values():
        for provider, (label, evidence) in provider_map.items():
            canonical = _normalize_selection_label(label, family_label)
            if canonical is None:
                continue
            key = legacy.normalized_key(canonical)
            normalized[key][provider] = (canonical, evidence)

    # One final body-aware reconciliation after SUV/Sport Utility and Van/Minivan
    # aliases have been normalized. This prevents synonymous body words from
    # manufacturing separate trim rows on single-body vehicles.
    body_styles = {
        body
        for provider_map in normalized.values()
        for label, _ in provider_map.values()
        if (body := v3._split_body_prefix(label)[0]) is not None
    }
    if len(body_styles) <= 1:
        collapsed: dict[str, dict[str, tuple[str, dict[str, object]]]] = defaultdict(dict)
        for provider_map in normalized.values():
            for provider, (label, evidence) in provider_map.items():
                body, grade = v3._split_body_prefix(label)
                canonical = grade if body and grade else label
                key = legacy.normalized_key(canonical)
                collapsed[key][provider] = (canonical, evidence)
        normalized = collapsed

    # Collapse source "Base" decorations only when the concise grade exists.
    keys = set(normalized)
    base_collapsed: dict[str, dict[str, tuple[str, dict[str, object]]]] = defaultdict(dict)
    for key, provider_map in normalized.items():
        target = key
        if key.endswith(" base"):
            candidate = key[: -len(" base")].strip()
            if candidate in keys:
                target = candidate
        for provider, observation in provider_map.items():
            base_collapsed[target][provider] = observation
    normalized = base_collapsed

    # KBB sometimes treats "Sport Coupe/Wagon" as body-style wording. Collapse
    # a trailing "Sport" only when the same shorter grade is independently
    # present in this model-year.
    keys = set(normalized)
    remapped: dict[str, dict[str, tuple[str, dict[str, object]]]] = defaultdict(dict)
    for key, provider_map in normalized.items():
        target = key
        if key.endswith(" sport"):
            candidate = key[: -len(" sport")].strip()
            if candidate in keys:
                target = candidate
        for provider, observation in provider_map.items():
            remapped[target][provider] = observation
    normalized = remapped

    # If a verbose configuration string survives but a concise observed trim is
    # contained in it, keep the concise trim. This is limited to labels carrying
    # explicit option/transmission/seating markers; genuine marketed extensions
    # such as TRD Sport, 2.0T, V6, Black Edition, etc. are not collapsed.
    keys = set(normalized)
    final: dict[str, dict[str, tuple[str, dict[str, object]]]] = defaultdict(dict)
    for key, provider_map in normalized.items():
        target = key
        labels = [item[0] for item in provider_map.values()]
        if any(_label_has_config_marker(label) for label in labels):
            key_tokens = key.split()
            candidates = [
                candidate
                for candidate in keys
                if candidate != key
                and len(candidate.split()) < len(key_tokens)
                and all(token in key_tokens for token in candidate.split())
            ]
            if candidates:
                target = max(candidates, key=lambda candidate: len(candidate.split()))
        for provider, observation in provider_map.items():
            final[target][provider] = observation

    return dict(final)


async def export_json(path: str) -> None:
    await v3.export_json(path)
    destination = Path(path)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    scope = payload.setdefault("scope", {})
    scope["identity_label_strategy"] = "marketed_selection_v4_2"
    model_rows = payload.get("models", [])
    empty_trim_models = sum(
        1 for model in model_rows if isinstance(model, dict) and not model.get("trims")
    )
    trim_rows = sum(
        len(model.get("trims", []))
        for model in model_rows
        if isinstance(model, dict)
    )
    one_source_trims = sum(
        1
        for model in model_rows
        if isinstance(model, dict)
        for trim in model.get("trims", [])
        if isinstance(trim, dict) and trim.get("source_count") == 1
    )
    residual_drivetrain_labels = sum(
        1
        for model in model_rows
        if isinstance(model, dict)
        for trim in model.get("trims", [])
        if isinstance(trim, dict)
        and _DRIVETRAIN_TOKEN_RE.search(str(trim.get("trim", "")))
    )
    residual_config_labels = sum(
        1
        for model in model_rows
        if isinstance(model, dict)
        for trim in model.get("trims", [])
        if isinstance(trim, dict)
        and _CONFIG_MARKER_RE.search(str(trim.get("trim", "")))
    )
    payload["quality_summary"] = {
        "model_year_rows": len(model_rows),
        "marketed_selection_rows": trim_rows,
        "model_years_without_trim_rows": empty_trim_models,
        "one_source_selection_rows": one_source_trims,
        "residual_drivetrain_label_rows": residual_drivetrain_labels,
        "residual_config_marker_rows": residual_config_labels,
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=False),
        encoding="utf-8",
    )


def install_v4_behavior() -> None:
    v3.install_v3_behavior()

    # Canonicalize synonymous body labels before V3 decides whether body style
    # is a real selection dimension.
    v3._BODY_PREFIX_KEYS = dict(_BODY_PREFIX_KEYS_V4)

    v2.canonicalize_model_inventory = canonicalize_model_inventory
    v2._source_model_aliases = _source_model_aliases
    v3.model_variants = model_variants
    v3.model_variant = model_variant
    v3._strict_trim_value = _strict_trim_value
    v3._finalize_trim_observations = _finalize_trim_observations
    legacy.combine_trim_variant = combine_trim_variant

    # V3 extractors resolve these globals at run time.
    legacy.trim_from_kbb_style = v3.trim_from_kbb_style
    legacy.trim_from_carsdirect_style = v3.trim_from_carsdirect_style
    legacy.extract_kbb_trims = v3.extract_kbb_trims
    legacy.extract_carsdirect_trims = v3.extract_carsdirect_trims
    legacy.collect_make_year = v3._collect_make_year
    legacy.export_json = export_json


def main() -> None:
    install_v4_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
