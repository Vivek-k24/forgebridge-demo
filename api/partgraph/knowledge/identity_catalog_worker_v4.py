from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v2 as v2
from . import identity_catalog_worker_v3 as v3

# V4 is a cache-reconciliation pass over V3. It does not add technical specs.
# It fixes source-presentation artifacts exposed by the September 6 catalog audit.

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
    r"(?:\bw/|\b\d+\s+passenger\b|auto access seat|"
    r"\bpackage\b|\bpkg\b|navigation|nav system|honda sensing|"
    r"\bautomatic\b|\bmanual\b|\bcvt\b|\b50 state\b|"
    r"\binterior\b|\bleather\b)",
    re.I,
)
_TRAILING_OPTION_RE = re.compile(r"\s+w/.*$", re.I)
_PASSENGER_RE = re.compile(
    r"\s+(?:7|8)\s+Passenger(?:\s+Auto Access Seat)?$",
    re.I,
)
_AUTO_ACCESS_RE = re.compile(r"\s+Auto Access Seat$", re.I)
_LEADING_TRANSMISSION_RE = re.compile(
    r"^w/(?:"
    r"(?:4|5|6|7|8|9|10)[- ]?(?:Speed|Spd)\s+(?:Automatic|Manual)|"
    r"Automatic|Manual|CVT"
    r")\s+",
    re.I,
)

_CURRENT_MAKE: str | None = None
_HYBRID_FAMILIES: set[tuple[str, str]] = set()


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
    global _CURRENT_MAKE
    _CURRENT_MAKE = make
    inventory = _V2_CANONICALIZE(
        nhtsa_models,
        fueleconomy_models,
        make=make,
        year=year,
    )
    if make:
        for model, provider_labels in inventory.items():
            if _provider_labels_have_hybrid(provider_labels):
                _HYBRID_FAMILIES.add((make, legacy.normalized_key(model)))
    return inventory


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

    if (
        _CURRENT_MAKE
        and (_CURRENT_MAKE, legacy.normalized_key(canonical_model)) in _HYBRID_FAMILIES
    ):
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


def _normalize_selection_label(label: str) -> str | None:
    body, grade = v3._split_body_prefix(label)
    grade = grade or label
    key = legacy.normalized_key(grade)

    if key in _STANDALONE_PACKAGE_KEYS:
        return None

    if key.startswith("base "):
        suffix = key[len("base ") :]
        if suffix in _SPECIAL_VARIANTS:
            return _SPECIAL_VARIANTS[suffix]

    # Transmission/options/seating are configuration dimensions, not trims.
    grade = _LEADING_TRANSMISSION_RE.sub("", grade).strip()
    grade = _TRAILING_OPTION_RE.sub("", grade).strip()
    grade = _PASSENGER_RE.sub("", grade).strip()
    grade = _AUTO_ACCESS_RE.sub("", grade).strip()

    # Preserve the marketed grade spelling used by the accepted Honda fixture.
    grade = re.sub(r"\bSport L\b", "Sport-L", grade, flags=re.I)

    if not grade:
        return None
    if legacy.normalized_key(grade) in _STANDALONE_PACKAGE_KEYS:
        return None
    if legacy.normalized_key(grade) in _SPECIAL_VARIANTS:
        body = None

    return v3._selection_label(grade, body)


def _label_has_config_marker(label: str) -> bool:
    return bool(_CONFIG_MARKER_RE.search(label))


def _finalize_trim_observations(
    observations: dict[str, dict[str, tuple[str, dict[str, object]]]],
    provider_labels: dict[str, list[str]],
) -> dict[str, dict[str, tuple[str, dict[str, object]]]]:
    base = _V3_FINALIZE(observations, provider_labels)

    normalized: dict[str, dict[str, tuple[str, dict[str, object]]]] = defaultdict(dict)
    for provider_map in base.values():
        for provider, (label, evidence) in provider_map.items():
            canonical = _normalize_selection_label(label)
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
    scope["identity_label_strategy"] = "marketed_selection_v4"
    model_rows = payload.get("models", [])
    empty_trim_models = sum(
        1 for model in model_rows if isinstance(model, dict) and not model.get("trims")
    )
    trim_rows = sum(
        len(model.get("trims", []))
        for model in model_rows
        if isinstance(model, dict)
    )
    payload["quality_summary"] = {
        "model_year_rows": len(model_rows),
        "marketed_selection_rows": trim_rows,
        "model_years_without_trim_rows": empty_trim_models,
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
