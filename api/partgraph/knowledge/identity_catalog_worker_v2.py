from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
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
    (("a", "spec"), "A-Spec"),
    (("hybrid",), "Hybrid"),
    (("hev",), "Hybrid"),
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
_COMPONENT_RE = re.compile(r"[a-z]+|\d+")
_TRIM_BODY_ONLY = {
    "convertible",
    "coupe",
    "hatchback",
    "minivan",
    "pickup",
    "roadster",
    "sedan",
    "sport utility",
    "suv",
    "targa",
    "van",
    "wagon",
}
_TRIM_BODY_SUFFIX_RE = re.compile(
    r"\s+(?:Sport Utility|SUV|Coupe|Sedan|Hatchback|Wagon|Convertible|"
    r"Roadster|Minivan|Van|Pickup|Targa)"
    r"(?:\s+\dD)?(?:\s+\d+(?:\.\d+)?\s*ft)?$",
    re.I,
)
_TRIM_REJECT_RE = re.compile(
    r"(?:"
    r"consumer reviews|learn more about|depreciation|cost to own|"
    r"select a trim|choose a trim|starting at|"
    r"\$\s?\d|\bmpg\b|\bmpge\b|\bkwh\b|\bcu\s*ft\b|"
    r"\brpm\b|\blbs?\b|\bhp\b|\bmiles\b|\bhours\b"
    r")",
    re.I,
)

_ORIGINAL_KBB_STYLE = legacy.trim_from_kbb_style
_ORIGINAL_CARSDIRECT_STYLE = legacy.trim_from_carsdirect_style
_ORIGINAL_FUELECONOMY_MODELS = legacy._fueleconomy_models


def _components(value: str) -> tuple[str, ...]:
    return tuple(_COMPONENT_RE.findall(value.casefold()))


def _clean_model_label(value: str) -> str:
    return legacy._SPACE_RE.sub(" ", value).strip()


def _historical_model_alias(make: str | None, year: int | None, label: str) -> str | None:
    if make == "Toyota" and label.casefold().startswith("scion "):
        # vPIC can expose Scion products under Toyota's manufacturer record.
        # Scion is outside the explicitly requested six-make catalog.
        return None
    if make == "Toyota" and legacy.normalized_key(label) == "corolla matrix":
        return "Matrix"
    if make == "Subaru" and legacy.normalized_key(label) == "b9 tribeca" and year is not None:
        return "Tribeca" if year >= 2008 else "B9 Tribeca"

    # vPIC sometimes appends a powertrain annotation to an otherwise distinct
    # marketed model name. The annotation is not part of the canonical model.
    if make == "Toyota":
        label = re.sub(r"\s*\(PHEV\)\s*$", "", label, flags=re.I).strip()
    return label


def _variant_from_remainder(tokens: tuple[str, ...]) -> str | None:
    remainder = tuple(token for token in tokens if token not in _DRIVETRAIN_SUFFIX_TOKENS)
    if not remainder:
        return None
    for suffix, label in _MODEL_TRIM_SUFFIXES:
        if remainder == suffix:
            return label
    return None


def _nhtsa_canonical_map(
    nhtsa_models: list[str],
    *,
    make: str | None = None,
    year: int | None = None,
) -> dict[tuple[str, ...], str]:
    cleaned: dict[tuple[str, ...], str] = {}
    original_for_key: dict[tuple[str, ...], str] = {}
    for raw in nhtsa_models:
        label = _clean_model_label(raw)
        if not label:
            continue
        alias = _historical_model_alias(make, year, label)
        if alias is None:
            continue
        key = _components(label)
        if key:
            cleaned.setdefault(_components(alias), alias)
            original_for_key[key] = alias

    result: dict[tuple[str, ...], str] = {}
    for raw in nhtsa_models:
        label = _clean_model_label(raw)
        if not label:
            continue
        alias = _historical_model_alias(make, year, label)
        if alias is None:
            continue
        raw_tokens = _components(label)
        alias_tokens = _components(alias)
        canonical = alias
        for suffix, _variant in _MODEL_TRIM_SUFFIXES:
            if len(alias_tokens) <= len(suffix) or alias_tokens[-len(suffix) :] != suffix:
                continue
            base_tokens = alias_tokens[: -len(suffix)]
            if base_tokens in cleaned:
                canonical = cleaned[base_tokens]
                break
        result[raw_tokens] = canonical
        result.setdefault(alias_tokens, canonical)

    # Preserve aliases introduced above even when their raw tokenization differs.
    for raw_tokens, alias in original_for_key.items():
        result.setdefault(raw_tokens, alias)
    return result


def _longest_model_match(
    label: str,
    nhtsa_map: dict[tuple[str, ...], str],
) -> str | None:
    source_tokens = _components(label)
    if source_tokens in nhtsa_map:
        return nhtsa_map[source_tokens]

    canonical_tokens: dict[tuple[str, ...], str] = {}
    for canonical in nhtsa_map.values():
        canonical_tokens.setdefault(_components(canonical), canonical)

    matches: list[tuple[int, int, str]] = []
    for candidate_tokens, canonical in canonical_tokens.items():
        if not candidate_tokens or len(source_tokens) < len(candidate_tokens):
            continue
        width = len(candidate_tokens)
        for index in range(len(source_tokens) - width + 1):
            if source_tokens[index : index + width] == candidate_tokens:
                # Prefer the longest family name, then the earliest occurrence.
                matches.append((width, -index, canonical))
                break
    if not matches:
        return None
    matches.sort(reverse=True)
    return matches[0][2]


def canonicalize_model_inventory(
    nhtsa_models: list[str],
    fueleconomy_models: list[str],
    *,
    make: str | None = None,
    year: int | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Map source configuration names into consumer model families.

    NHTSA road-vehicle names are the family anchor. FuelEconomy labels are often
    configurations (for example ES 350, TLX AWD A-SPEC, Civic 5Dr Type R, or
    wheel/drivetrain variants), so a boundary-aware longest family match folds
    those labels into the model instead of inventing extra models.
    """

    inventory: dict[str, dict[str, list[str]]] = {}
    nhtsa_map = _nhtsa_canonical_map(nhtsa_models, make=make, year=year)

    for raw in nhtsa_models:
        label = _clean_model_label(raw)
        alias = _historical_model_alias(make, year, label)
        if not label or alias is None:
            continue
        canonical = nhtsa_map.get(_components(label), alias)
        inventory.setdefault(canonical, {}).setdefault("nhtsa_vpic", []).append(label)

    for raw in fueleconomy_models:
        label = _clean_model_label(raw)
        if not label:
            continue
        canonical = _longest_model_match(label, nhtsa_map)

        # Lexus' NHTSA family list is normally ES/GS/GX/IS/etc., while the EPA
        # model menu commonly emits ES 350, GX 550, RX 500h, and similar labels.
        # If one family is temporarily absent from vPIC, keep the family token
        # rather than turning an engine designation into a separate model.
        if canonical is None and make == "Lexus":
            match = re.match(r"^\s*([A-Za-z]{2,3})\s+\d", label)
            if match:
                canonical = match.group(1).upper()

        canonical = canonical or label
        inventory.setdefault(canonical, {}).setdefault("fueleconomy_gov", []).append(label)

    for provider_map in inventory.values():
        for provider, labels in provider_map.items():
            provider_map[provider] = sorted(dict.fromkeys(labels), key=str.casefold)
    return inventory


def model_variant(canonical_model: str, source_model: str) -> str | None:
    base = _components(canonical_model)
    source = _components(source_model)
    if source == base:
        return None

    # Find the canonical family inside a configuration-style source label, then
    # inspect only the remaining tokens. This supports Civic 5Dr Type R and
    # TLX AWD A-SPEC without treating the body/drivetrain text as the trim.
    for index in range(len(source) - len(base) + 1):
        if source[index : index + len(base)] != base:
            continue
        remainder = source[:index] + source[index + len(base) :]
        ignored = {
            "2dr",
            "3dr",
            "4dr",
            "5dr",
            "2",
            "3",
            "4",
            "5",
            "dr",
            "door",
            "doors",
            "wagon",
            "coupe",
            "sedan",
            "hatchback",
            "convertible",
            "truck",
        }
        remainder = tuple(token for token in remainder if token not in ignored)
        variant = _variant_from_remainder(remainder)
        if variant is not None:
            return variant
    return None


def _strict_trim_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = legacy._SPACE_RE.sub(" ", value).strip(" -|\t\r\n")
    cleaned = _TRIM_BODY_SUFFIX_RE.sub("", cleaned).strip()
    if not cleaned:
        return None
    key = legacy.normalized_key(cleaned)
    if key in _TRIM_BODY_ONLY or _TRIM_REJECT_RE.search(cleaned):
        return None
    if len(cleaned) > 100:
        return None
    return cleaned


def trim_from_kbb_style(style: str) -> str | None:
    return _strict_trim_value(_ORIGINAL_KBB_STYLE(style))


def trim_from_carsdirect_style(style: str) -> str | None:
    return _strict_trim_value(_ORIGINAL_CARSDIRECT_STYLE(style))


def _trim_alias_key(key: str, known_keys: set[str]) -> str:
    tokens = key.split()
    # KBB sometimes leaves a body/style descriptor after stripping the final
    # body word (for example GS-R Sport Coupe -> GS-R Sport). Collapse it only
    # when another provider actually observed the shorter trim.
    for suffix in (
        ("sport",),
        ("targa",),
        ("automatic",),
        ("manual",),
        ("v6",),
        ("v8",),
        ("i4",),
    ):
        if len(tokens) <= len(suffix) or tuple(tokens[-len(suffix) :]) != suffix:
            continue
        candidate = " ".join(tokens[: -len(suffix)])
        if candidate in known_keys:
            return candidate
    return key


def _source_model_aliases(
    canonical_model: str,
    provider_labels: dict[str, list[str]],
) -> list[str]:
    aliases = [canonical_model]
    # Consumer sites commonly expose dedicated pages for these model variants.
    # Configuration-heavy FuelEconomy names such as wheel sizes and AWD labels
    # are deliberately not used as page slugs.
    for value in provider_labels.get("nhtsa_vpic", []):
        if model_variant(canonical_model, value) is not None:
            aliases.append(value)
    for value in provider_labels.get("fueleconomy_gov", []):
        if model_variant(canonical_model, value) is not None:
            aliases.append(value)
    return sorted(dict.fromkeys(aliases), key=lambda value: (value != canonical_model, value.casefold()))


def _fueleconomy_models(
    make: str,
    year: int,
    refresh: bool,
) -> tuple[list[str], dict[str, object]]:
    models, evidence = _ORIGINAL_FUELECONOMY_MODELS(make, year, refresh)
    if evidence.get("status") not in {"success", "cached"}:
        raise RuntimeError(
            "FuelEconomy model enumeration incomplete; refusing to mark "
            f"{year} {make} complete ({evidence.get('status', 'failed')})"
        )
    return models, evidence


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
        raise RuntimeError(f"invalid NHTSA {vehicle_type} model payload: {exc}") from exc


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


async def _collect_make_year(make: str, year: int, *, refresh: bool) -> None:
    progress = await legacy._progress(make, year)
    if progress.status == "completed" and not refresh:
        print(f"SKIP {year} {make}: already completed")
        return

    async with legacy.session_factory() as session:
        async with session.begin():
            row = await session.get(legacy.CatalogIdentityProgress, progress.id)
            if row is None:
                return
            row.status = "running"
            row.started_at = legacy._now()
            row.completed_at = None
            row.last_error = None

    try:
        nhtsa_models, nhtsa_evidence = await asyncio.to_thread(_nhtsa_models, make, year, refresh)
        fueleconomy_models, fueleconomy_evidence = await asyncio.to_thread(
            _fueleconomy_models, make, year, refresh
        )
        inventory = canonicalize_model_inventory(
            nhtsa_models,
            fueleconomy_models,
            make=make,
            year=year,
        )

        if refresh:
            async with legacy.session_factory() as session:
                async with session.begin():
                    await session.execute(
                        legacy.delete(legacy.CatalogIdentityModel).where(
                            legacy.CatalogIdentityModel.market == legacy.US_IDENTITY_MARKET,
                            legacy.CatalogIdentityModel.year == year,
                            legacy.CatalogIdentityModel.make_key == legacy.normalized_key(make),
                        )
                    )

        unique_trim_keys: set[tuple[str, str]] = set()
        unresolved_models: list[str] = []
        accepted_models = 0
        summaries = {
            "kbb": {"success": 0, "not_found": 0, "blocked": 0, "failed": 0},
            "carsdirect": {"success": 0, "not_found": 0, "blocked": 0, "failed": 0},
        }

        for model, provider_labels in sorted(inventory.items(), key=lambda item: item[0].casefold()):
            # Fetch and normalize consumer trim observations before deciding that
            # a one-source model-year belongs in the canonical catalog.
            trim_observations: dict[str, dict[str, tuple[str, dict[str, object]]]] = defaultdict(dict)
            consumer_model_evidence: dict[str, list[dict[str, object]]] = defaultdict(list)

            # Configuration labels can themselves provide conservative trim
            # variants such as Hybrid, Si, Type R, Type S, or A-Spec.
            for provider in ("nhtsa_vpic", "fueleconomy_gov"):
                for source_model in provider_labels.get(provider, []):
                    variant = model_variant(model, source_model)
                    if variant is None:
                        continue
                    evidence = {
                        "status": "source_label",
                        "source_model": source_model,
                        "model_variant": variant,
                    }
                    trim_observations[legacy.normalized_key(variant)][provider] = (
                        variant,
                        evidence,
                    )

            for source_model in _source_model_aliases(model, provider_labels):
                for provider, fetcher in (
                    ("kbb", legacy._kbb_trims),
                    ("carsdirect", legacy._carsdirect_trims),
                ):
                    trims, evidence = await asyncio.to_thread(
                        fetcher, make, source_model, year, refresh
                    )
                    status = str(evidence.get("status", "failed"))
                    summary_key = "success" if status in {"success", "cached"} else status
                    if summary_key in summaries[provider]:
                        summaries[provider][summary_key] += 1
                    if status == "failed":
                        raise RuntimeError(
                            f"{provider} request failed for {year} {make} {source_model}; "
                            "refusing to mark the make/year complete"
                        )

                    variant = model_variant(model, source_model)
                    canonical_trims = {
                        combined
                        for trim in trims
                        if (strict := _strict_trim_value(trim)) is not None
                        if (combined := legacy.combine_trim_variant(strict, variant)) is not None
                    }
                    if variant is not None and not canonical_trims and status in {"success", "cached"}:
                        canonical_trims.add(variant)

                    if canonical_trims:
                        enriched = dict(evidence)
                        enriched["source_model"] = source_model
                        if variant is not None:
                            enriched["model_variant"] = variant
                        consumer_model_evidence[provider].append(enriched)
                        for trim in canonical_trims:
                            trim_observations[legacy.normalized_key(trim)][provider] = (trim, enriched)

            # Reconcile safe provider presentation differences such as
            # "GS-R Sport" vs "GS-R" only when the shorter form was actually
            # observed elsewhere.
            all_keys = set(trim_observations)
            remapped: dict[str, dict[str, tuple[str, dict[str, object]]]] = defaultdict(dict)
            for key, provider_map in trim_observations.items():
                target_key = _trim_alias_key(key, all_keys)
                for provider, observation in provider_map.items():
                    remapped[target_key][provider] = observation
            trim_observations = remapped

            has_fueleconomy = "fueleconomy_gov" in provider_labels
            has_consumer = bool(consumer_model_evidence)
            nhtsa_future_candidate = year == legacy.US_IDENTITY_YEAR_MAX and "nhtsa_vpic" in provider_labels
            if not (has_fueleconomy or has_consumer or nhtsa_future_candidate):
                unresolved_models.append(model)
                continue

            model_source_labels = {provider: list(labels) for provider, labels in provider_labels.items()}
            source_evidence: dict[str, dict[str, object]] = {
                "nhtsa_vpic": nhtsa_evidence,
                "fueleconomy_gov": fueleconomy_evidence,
            }
            for provider, captures in consumer_model_evidence.items():
                model_source_labels.setdefault(provider, [model])
                source_evidence[provider] = {
                    "status": "trim_observed",
                    "captures": captures,
                }

            model_row = await legacy._upsert_model(
                make,
                year,
                model,
                model_source_labels,
                source_evidence,
            )
            accepted_models += 1

            for key, provider_map in trim_observations.items():
                # Prefer a corroborated provider label; normalized punctuation
                # differences still share the same database trim key.
                labels = [item[0] for item in provider_map.values()]
                canonical_label = min(labels, key=lambda value: (len(value), value.casefold()))
                for provider, (_label, evidence) in provider_map.items():
                    await legacy._upsert_trim(model_row, canonical_label, provider, evidence)
                unique_trim_keys.add((legacy.normalized_key(model), key))

        async with legacy.session_factory() as session:
            async with session.begin():
                row = await session.get(legacy.CatalogIdentityProgress, progress.id)
                if row is None:
                    return
                row.status = "completed"
                row.models_found = accepted_models
                row.trims_found = len(unique_trim_keys)
                row.source_summary = {
                    "nhtsa_vpic": nhtsa_evidence,
                    "fueleconomy_gov": fueleconomy_evidence,
                    **summaries,
                    "unresolved_source_only_models": sorted(unresolved_models, key=str.casefold),
                    "unresolved_source_only_model_count": len(unresolved_models),
                }
                row.completed_at = legacy._now()
        print(
            f"PASS {year} {make}: {accepted_models} canonical models, "
            f"{len(unique_trim_keys)} canonical model-trim rows, "
            f"{len(unresolved_models)} unresolved source-only model candidates"
        )
    except Exception as exc:
        async with legacy.session_factory() as session:
            async with session.begin():
                row = await session.get(legacy.CatalogIdentityProgress, progress.id)
                if row is not None:
                    row.status = "failed"
                    row.last_error = str(exc)[:2000]
        print(f"FAIL {year} {make}: {exc}")


def install_v2_behavior() -> None:
    # The original worker owns persistence, status, export, and resumability.
    # Override source parsing, taxonomy, and the make/year collection decision so
    # raw provider configurations cannot inflate the canonical model catalog.
    legacy.trim_from_kbb_style = trim_from_kbb_style
    legacy.trim_from_carsdirect_style = trim_from_carsdirect_style
    legacy._nhtsa_models = _nhtsa_models
    legacy._fueleconomy_models = _fueleconomy_models
    legacy.canonicalize_model_inventory = canonicalize_model_inventory
    legacy.model_variant = model_variant
    legacy._source_model_aliases = _source_model_aliases
    legacy.collect_make_year = _collect_make_year


def main() -> None:
    install_v2_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
