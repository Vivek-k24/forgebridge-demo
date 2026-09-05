from __future__ import annotations

import json
from urllib.parse import quote

from . import identity_catalog_worker as legacy

# vPIC contains motorcycles, ATVs, low-speed vehicles, buses, trailers, and other
# manufacturer products under the same make. PartGraph's current identity phase
# is explicitly the US consumer road-vehicle catalog, so only these light road
# vehicle classes are allowed to seed model families.
NHTSA_AUTOMOBILE_VEHICLE_TYPES = (
    "Passenger Car",
    "Multipurpose Passenger Vehicle (MPV)",
    "Truck",
)

# These are model-name suffixes that PartGraph intentionally represents as trims
# or configuration variants when the same make/year also exposes the base model.
# Keep Si and Type R distinct; never collapse them into one performance bucket.
_MODEL_TRIM_SUFFIXES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("type", "r"), "Type R"),
    (("type", "s"), "Type S"),
    (("hybrid",), "Hybrid"),
    (("si",), "Si"),
)
_DRIVETRAIN_SUFFIX_TOKENS = {
    "2wd",
    "4wd",
    "awd",
    "fwd",
    "rwd",
    "4x2",
    "4x4",
}


def _variant_from_remainder(tokens: tuple[str, ...]) -> str | None:
    remainder = tuple(token for token in tokens if token not in _DRIVETRAIN_SUFFIX_TOKENS)
    if not remainder:
        return None
    for suffix, label in _MODEL_TRIM_SUFFIXES:
        if remainder == suffix:
            return label
    return None


def _is_supported_configuration_suffix(tokens: tuple[str, ...]) -> bool:
    if not tokens:
        return False
    remainder = tuple(token for token in tokens if token not in _DRIVETRAIN_SUFFIX_TOKENS)
    if not remainder:
        return True
    return any(remainder == suffix for suffix, _ in _MODEL_TRIM_SUFFIXES)


def _nhtsa_canonical_map(nhtsa_models: list[str]) -> dict[tuple[str, ...], str]:
    cleaned: dict[tuple[str, ...], str] = {}
    for raw in nhtsa_models:
        label = legacy._SPACE_RE.sub(" ", raw).strip()
        tokens = legacy._tokens(label)
        if label and tokens:
            cleaned.setdefault(tokens, label)

    result: dict[tuple[str, ...], str] = {}
    for tokens, label in cleaned.items():
        canonical = label
        for suffix, _variant in _MODEL_TRIM_SUFFIXES:
            if len(tokens) <= len(suffix) or tokens[-len(suffix) :] != suffix:
                continue
            base_tokens = tokens[: -len(suffix)]
            if base_tokens in cleaned:
                canonical = cleaned[base_tokens]
                break
        result[tokens] = canonical
    return result


def canonicalize_model_inventory(
    nhtsa_models: list[str],
    fueleconomy_models: list[str],
) -> dict[str, dict[str, list[str]]]:
    """Build consumer model families while retaining raw source labels.

    NHTSA road-vehicle names are the model-family anchor. Known configuration
    suffixes such as Hybrid, Si, Type R, and Type S are attached to the base
    model only when that base model exists for the same make/year. FuelEconomy
    drivetrain/configuration suffixes are mapped to the same family. Genuine
    model names such as Prius Prime remain distinct.
    """

    inventory: dict[str, dict[str, list[str]]] = {}
    nhtsa_map = _nhtsa_canonical_map(nhtsa_models)

    for raw in nhtsa_models:
        label = legacy._SPACE_RE.sub(" ", raw).strip()
        if not label:
            continue
        canonical = nhtsa_map.get(legacy._tokens(label), label)
        inventory.setdefault(canonical, {}).setdefault("nhtsa_vpic", []).append(label)

    canonical_token_map: dict[tuple[str, ...], str] = {}
    for raw_tokens, canonical in nhtsa_map.items():
        canonical_token_map[raw_tokens] = canonical
        canonical_token_map.setdefault(legacy._tokens(canonical), canonical)
    ordered_nhtsa = sorted(canonical_token_map, key=len, reverse=True)

    for raw in fueleconomy_models:
        label = legacy._SPACE_RE.sub(" ", raw).strip()
        if not label:
            continue
        raw_tokens = legacy._tokens(label)
        canonical = canonical_token_map.get(raw_tokens)
        if canonical is None:
            for candidate_tokens in ordered_nhtsa:
                if len(raw_tokens) <= len(candidate_tokens):
                    continue
                if raw_tokens[: len(candidate_tokens)] != candidate_tokens:
                    continue
                suffix = raw_tokens[len(candidate_tokens) :]
                if _is_supported_configuration_suffix(suffix):
                    canonical = canonical_token_map[candidate_tokens]
                    break
        if canonical is None:
            key = legacy.normalized_key(label)
            canonical = next(
                (name for name in inventory if legacy.normalized_key(name) == key),
                label,
            )
        inventory.setdefault(canonical, {}).setdefault("fueleconomy_gov", []).append(label)

    for provider_map in inventory.values():
        for provider, labels in provider_map.items():
            provider_map[provider] = sorted(dict.fromkeys(labels), key=str.casefold)
    return inventory


def model_variant(canonical_model: str, source_model: str) -> str | None:
    base = legacy._tokens(canonical_model)
    source = legacy._tokens(source_model)
    if len(source) <= len(base) or source[: len(base)] != base:
        return None
    return _variant_from_remainder(source[len(base) :])


def _parse_nhtsa_models(raw: bytes, vehicle_type: str) -> list[str]:
    try:
        payload = json.loads(raw)
        results = payload.get("Results", []) if isinstance(payload, dict) else []
        models = [
            str(item.get("Model_Name", "")).strip()
            for item in results
            if isinstance(item, dict) and item.get("Model_Name")
        ]
        return sorted(dict.fromkeys(models), key=str.casefold)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise RuntimeError(
            f"invalid NHTSA {vehicle_type} model payload: {exc}"
        ) from exc


def _nhtsa_models(
    make: str,
    year: int,
    refresh: bool,
) -> tuple[list[str], dict[str, object]]:
    """Enumerate only consumer road-vehicle NHTSA model classes.

    All three vehicle-type requests must succeed (or come from cache). A network
    outage therefore marks the make/year failed instead of silently recording a
    completed 0-model year that would later be skipped.
    """

    all_models: set[str] = set()
    captures: dict[str, dict[str, object]] = {}
    failed_types: list[str] = []

    for vehicle_type in NHTSA_AUTOMOBILE_VEHICLE_TYPES:
        url = (
            f"{legacy.settings.nhtsa_base_url}/GetModelsForMakeYear/make/{quote(make)}/"
            f"modelyear/{year}/vehicletype/{quote(vehicle_type, safe='')}?format=json"
        )
        raw, evidence = legacy._fetch_cached(
            "nhtsa_vpic",
            make,
            year,
            url,
            accept="application/json",
            suffix="json",
            refresh=refresh,
        )
        captures[vehicle_type] = evidence
        if raw is None:
            failed_types.append(vehicle_type)
            continue
        all_models.update(_parse_nhtsa_models(raw, vehicle_type))

    if failed_types:
        details = ", ".join(
            f"{vehicle_type}={captures[vehicle_type].get('status', 'failed')}"
            for vehicle_type in failed_types
        )
        raise RuntimeError(
            "NHTSA road-vehicle model enumeration incomplete; refusing to mark "
            f"{year} {make} complete ({details})"
        )

    statuses = {str(item.get("status", "failed")) for item in captures.values()}
    overall_status = "cached" if statuses == {"cached"} else "success"
    evidence: dict[str, object] = {
        "status": overall_status,
        "vehicle_type_scope": list(NHTSA_AUTOMOBILE_VEHICLE_TYPES),
        "captures": captures,
        "model_count": len(all_models),
    }
    return sorted(all_models, key=str.casefold), evidence


def install_v2_behavior() -> None:
    # The original worker owns persistence, trim scraping, status, export, and
    # resumability. Override only the model-boundary behavior so there is one
    # storage/collection implementation rather than a second divergent worker.
    legacy._nhtsa_models = _nhtsa_models
    legacy.canonicalize_model_inventory = canonicalize_model_inventory
    legacy.model_variant = model_variant


def main() -> None:
    install_v2_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
