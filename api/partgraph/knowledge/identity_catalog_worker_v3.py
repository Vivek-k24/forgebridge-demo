from __future__ import annotations

import asyncio
import html
import json
import re
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v2 as v2

# V3 keeps V2's road-vehicle/model-family boundary and tightens the final
# marketed selection labels. The identity catalog is still year + make + model
# + trim only; the dimension metadata below is descriptive and does not promote
# engine/transmission/performance facts into this phase.

_V2_MODEL_VARIANT = v2.model_variant
_V2_KBB_TRIM = v2.trim_from_kbb_style
_V2_CARSDIRECT_TRIM = v2.trim_from_carsdirect_style
_V2_KBB_EXTRACTOR = legacy.extract_kbb_trims
_V2_CARSDIRECT_EXTRACTOR = legacy.extract_carsdirect_trims

_BODY_STYLE_NAMES = (
    "Sport Utility",
    "Hatchback",
    "Convertible",
    "Roadster",
    "Minivan",
    "Sedan",
    "Coupe",
    "Wagon",
    "Pickup",
    "SUV",
    "Van",
)
_BODY_PREFIX_KEYS = {
    legacy.normalized_key(value): value
    for value in _BODY_STYLE_NAMES
}
_SPECIAL_STANDALONE_TRIMS = {
    "si",
    "type r",
    "type s",
    "a spec",
}
_PACKAGE_SUFFIXES = (
    ("2", "tone"),
    ("two", "tone"),
    ("towing",),
    ("tow",),
)
_REVIEW_RE = re.compile(r"\bconsumer reviews?\b", re.I)
_ENGINE_DISPLACEMENT_ONLY_RE = re.compile(r"^\d+(?:\.\d+)?\s*l$", re.I)
_KBB_TAG_RE = re.compile(r"<[^>]+>")
_KBB_BODY_RE = re.compile(
    r"\b(Sport Utility|Hatchback|Convertible|Roadster|Minivan|"
    r"Sedan|Coupe|Wagon|Pickup|SUV|Van)\b",
    re.I,
)
_CARSDIRECT_BODY_RE = re.compile(
    r"\b(?:[2-5]dr|[2-5]-door)\s+"
    r"(Sedan|Coupe|Hatchback|Wagon|SUV|Convertible|Roadster|Van|Pickup)\b",
    re.I,
)


def _visible_text(value: str) -> str:
    return legacy._SPACE_RE.sub(
        " ",
        html.unescape(_KBB_TAG_RE.sub(" ", value)),
    ).strip()


def _canonical_body_style(value: str | None) -> str | None:
    if value is None:
        return None
    key = legacy.normalized_key(value)
    return _BODY_PREFIX_KEYS.get(key)


def _body_style_from_text(value: str) -> str | None:
    match = _KBB_BODY_RE.search(_visible_text(value))
    return _canonical_body_style(match.group(1)) if match else None


def _body_style_from_carsdirect(value: str) -> str | None:
    match = _CARSDIRECT_BODY_RE.search(_visible_text(value))
    return _canonical_body_style(match.group(1)) if match else None


def _selection_label(grade: str, body_style: str | None) -> str:
    grade = legacy._SPACE_RE.sub(" ", grade).strip()
    if not body_style:
        return grade
    if legacy.normalized_key(grade) in _SPECIAL_STANDALONE_TRIMS:
        return grade
    return f"{body_style} {grade}"


def _strict_trim_value(value: str | None) -> str | None:
    cleaned = v2._strict_trim_value(value)
    if cleaned is None:
        return None
    if _REVIEW_RE.search(cleaned):
        return None
    if _ENGINE_DISPLACEMENT_ONLY_RE.fullmatch(cleaned):
        return None
    return cleaned


def trim_from_kbb_style(style: str) -> str | None:
    grade = _strict_trim_value(_V2_KBB_TRIM(style))
    if grade is None:
        return None
    return _selection_label(grade, _body_style_from_text(style))


def trim_from_carsdirect_style(style: str) -> str | None:
    grade = _strict_trim_value(_V2_CARSDIRECT_TRIM(style))
    if grade is None:
        return None
    return _selection_label(grade, _body_style_from_carsdirect(style))


def extract_kbb_trims(raw: bytes, make: str, model: str, year: int) -> list[str]:
    """Extract marketed grade/body labels from KBB links without page chrome."""

    text = raw.decode("utf-8", errors="replace")
    make_slug = re.escape(legacy.slug(make))
    model_slug = re.escape(legacy.slug(model))
    path = rf"/{make_slug}/{model_slug}/{year}/([^/?#\"']+)/?"
    anchor_pattern = re.compile(
        rf"<a\b[^>]*href=[\"'](?:https://www\.kbb\.com)?{path}[^\"']*[\"']"
        rf"[^>]*>(.*?)</a>",
        re.I | re.S,
    )
    trims: dict[str, str] = {}
    for match in anchor_pattern.finditer(text):
        style_slug = legacy.normalized_key(match.group(1).replace("-", " "))
        if style_slug in legacy._KBB_EXCLUDED_STYLE_KEYS:
            continue
        grade = _strict_trim_value(_V2_KBB_TRIM(match.group(2)))
        body_style = _body_style_from_text(match.group(2))
        if body_style is None:
            body_style = _body_style_from_text(match.group(1).replace("-", " "))
        if grade is not None:
            label = _selection_label(grade, body_style)
            trims.setdefault(legacy.normalized_key(label), label)

    # Keep V2's fallback coverage for historical pages whose useful style data is
    # not represented by modern style links. Final reconciliation removes the
    # generic label when richer body-specific labels exist for the same grade.
    for label in _V2_KBB_EXTRACTOR(raw, make, model, year):
        strict = _strict_trim_value(label)
        if strict is not None:
            trims.setdefault(legacy.normalized_key(strict), strict)
    return sorted(trims.values(), key=str.casefold)


def extract_carsdirect_trims(raw: bytes, model: str, year: int) -> list[str]:
    """Preserve body style from CarsDirect style strings where it is explicit."""

    text = raw.decode("utf-8", errors="replace")
    trims: dict[str, str] = {}

    for option in re.findall(r"<option\b[^>]*>(.*?)</option>", text, re.I | re.S):
        label = trim_from_carsdirect_style(option)
        if label is not None:
            trims.setdefault(legacy.normalized_key(label), label)

    visible = _visible_text(text)
    marker = "Select a Trim"
    marker_index = visible.casefold().find(marker.casefold())
    if marker_index >= 0:
        segment = visible[marker_index + len(marker) : marker_index + len(marker) + 6000]
        style_pattern = re.compile(
            r"(?<![A-Za-z0-9-])"
            r"([A-Za-z0-9][A-Za-z0-9+./&' -]{0,70}?)\s+"
            r"(?:[2-5]dr|2-door|3-door|4-door|5-door)\s+"
            r"(?:[A-Za-z-]+\s+){0,5}"
            r"(?:Sedan|Coupe|Hatchback|Wagon|SUV|Convertible|Roadster|Van|Pickup)",
            re.I,
        )
        for match in style_pattern.finditer(segment):
            label = trim_from_carsdirect_style(match.group(0))
            if label is not None:
                trims.setdefault(legacy.normalized_key(label), label)

    for label in _V2_CARSDIRECT_EXTRACTOR(raw, model, year):
        strict = _strict_trim_value(label)
        if strict is not None:
            trims.setdefault(legacy.normalized_key(strict), strict)
    return sorted(trims.values(), key=str.casefold)


def _remove_model_family(canonical_model: str, source_model: str) -> str:
    pattern = re.compile(re.escape(canonical_model), re.I)
    return pattern.sub(" ", source_model, count=1).strip()


def _marketed_variant_from_text(value: str) -> str | None:
    tokens = tuple(v2._components(value))
    tokens = tuple(
        token
        for token in tokens
        if token
        not in {
            *v2._DRIVETRAIN_SUFFIX_TOKENS,
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
            "sedan",
            "coupe",
            "hatchback",
            "wagon",
            "convertible",
            "roadster",
            "suv",
            "van",
            "pickup",
        }
    )
    if not tokens or all(token.isdigit() for token in tokens):
        return None

    normalized = " ".join(tokens)
    aliases = {
        "a spec": "A-Spec",
        "black": "Black Edition",
        "black edition": "Black Edition",
        "e fcev": "e:FCEV",
        "fcev": "e:FCEV",
        "hev": "Hybrid",
        "hybrid": "Hybrid",
        "si": "Si",
        "trail sport": "TrailSport",
        "trailsport": "TrailSport",
        "type r": "Type R",
        "type s": "Type S",
        "touring": "Touring",
        "elite": "Elite",
    }
    return aliases.get(normalized)


def model_variants(canonical_model: str, source_model: str) -> tuple[str, ...]:
    """Return conservative marketed variants encoded in a source model label."""

    variants: list[str] = []
    if (base := _V2_MODEL_VARIANT(canonical_model, source_model)) is not None:
        variants.append(base)

    remainder = _remove_model_family(canonical_model, source_model)
    if "/" in remainder:
        parts = remainder.split("/")
        for part in parts:
            if (variant := _marketed_variant_from_text(part)) is not None:
                variants.append(variant)
    elif (variant := _marketed_variant_from_text(remainder)) is not None:
        variants.append(variant)

    return tuple(dict.fromkeys(variants))


def model_variant(canonical_model: str, source_model: str) -> str | None:
    variants = model_variants(canonical_model, source_model)
    return variants[0] if variants else None


def _split_body_prefix(label: str) -> tuple[str | None, str]:
    key = legacy.normalized_key(label)
    for body_key, body in sorted(
        _BODY_PREFIX_KEYS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if key == body_key:
            return body, ""
        prefix = f"{body_key} "
        if key.startswith(prefix):
            words = label.split()
            body_words = len(body.split())
            return body, " ".join(words[body_words:]).strip()
    return None, label


def _source_labels_contain(
    provider_labels: dict[str, list[str]],
    token: str,
) -> bool:
    needle = token.casefold()
    return any(
        needle in label.casefold()
        for labels in provider_labels.values()
        for label in labels
    )


def _extension_base_key(key: str, suffix: tuple[str, ...]) -> str | None:
    tokens = key.split()
    if len(tokens) <= len(suffix):
        return None
    if tuple(tokens[-len(suffix) :]) != suffix:
        return None
    return " ".join(tokens[: -len(suffix)])


def _finalize_trim_observations(
    observations: dict[str, dict[str, tuple[str, dict[str, object]]]],
    provider_labels: dict[str, list[str]],
) -> dict[str, dict[str, tuple[str, dict[str, object]]]]:
    """Reconcile richer selection labels without turning packages into trims."""

    remapped: dict[str, dict[str, tuple[str, dict[str, object]]]] = defaultdict(dict)
    all_keys = set(observations)
    for key, provider_map in observations.items():
        target_key = v2._trim_alias_key(key, all_keys)
        for provider, observation in provider_map.items():
            remapped[target_key][provider] = observation

    observations = remapped
    body_styles = {
        body
        for provider_map in observations.values()
        for label, _evidence in provider_map.values()
        if (body := _split_body_prefix(label)[0]) is not None
    }

    # If the model has only one body style, body is not a useful selection
    # dimension (Accord Sedan -> Accord LX). If multiple body styles exist,
    # prefer the body-specific labels and remove their generic duplicates.
    body_aware: dict[str, dict[str, tuple[str, dict[str, object]]]] = defaultdict(dict)
    body_grades: set[str] = set()
    if len(body_styles) > 1:
        for provider_map in observations.values():
            for label, _evidence in provider_map.values():
                body, grade = _split_body_prefix(label)
                if body and grade:
                    body_grades.add(legacy.normalized_key(grade))

    for provider_map in observations.values():
        for provider, (label, evidence) in provider_map.items():
            body, grade = _split_body_prefix(label)
            canonical = label
            if len(body_styles) <= 1 and body and grade:
                canonical = grade
            elif (
                len(body_styles) > 1
                and body is None
                and legacy.normalized_key(label) in body_grades
            ):
                continue
            key = legacy.normalized_key(canonical)
            if key:
                body_aware[key][provider] = (canonical, evidence)

    keys = set(body_aware)
    has_specific_hybrid = any(key != "hybrid" and key.endswith(" hybrid") for key in keys)
    black_supported = _source_labels_contain(provider_labels, "black")

    final: dict[str, dict[str, tuple[str, dict[str, object]]]] = {}
    for key, provider_map in body_aware.items():
        if key == "hybrid" and has_specific_hybrid:
            continue

        hybrid_key = f"{key} hybrid"
        if (
            set(provider_map) <= {"fueleconomy_gov"}
            and hybrid_key in body_aware
            and set(body_aware[hybrid_key]) & {"kbb", "carsdirect"}
        ):
            continue

        # KBB occasionally emits truncated style strings such as "Touring S" or
        # "TrailSport S". Drop them only when the base trim is also observed.
        if key.endswith(" s") and not key.endswith("type s"):
            base_key = key[:-2].strip()
            if base_key in keys:
                continue

        drop_package_extension = False
        for suffix in _PACKAGE_SUFFIXES:
            base_key = _extension_base_key(key, suffix)
            if base_key and base_key in keys:
                drop_package_extension = True
                break
        if drop_package_extension:
            continue

        if key.endswith(" blackout"):
            base_key = key[: -len(" blackout")].strip()
            if base_key in keys and not black_supported:
                continue

        final[key] = provider_map

    return final


def identity_dimensions(trim: str) -> dict[str, str]:
    """Expose selection dimensions without changing the current database schema."""

    body_style, grade = _split_body_prefix(trim)
    grade = grade or trim
    powertrain_variant: str | None = None

    key = legacy.normalized_key(grade)
    if key.endswith(" hybrid"):
        powertrain_variant = "Hybrid"
        grade = re.sub(r"\s+Hybrid$", "", grade, flags=re.I).strip()
    elif "fcev" in key.split():
        powertrain_variant = "FCEV"
    elif key.endswith(" phev"):
        powertrain_variant = "PHEV"
        grade = re.sub(r"\s+PHEV$", "", grade, flags=re.I).strip()
    elif key.endswith(" ev") or key.endswith(" electric"):
        powertrain_variant = "Electric"

    payload = {"marketed_label": trim}
    if grade:
        payload["grade"] = grade
    if body_style:
        payload["body_style"] = body_style
    if powertrain_variant:
        payload["powertrain_variant"] = powertrain_variant
    return payload


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
        nhtsa_models, nhtsa_evidence = await asyncio.to_thread(
            v2._nhtsa_models,
            make,
            year,
            refresh,
        )
        fueleconomy_models, fueleconomy_evidence = await asyncio.to_thread(
            v2._fueleconomy_models,
            make,
            year,
            refresh,
        )
        inventory = v2.canonicalize_model_inventory(
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

        for model, provider_labels in sorted(
            inventory.items(),
            key=lambda item: item[0].casefold(),
        ):
            trim_observations: dict[
                str,
                dict[str, tuple[str, dict[str, object]]],
            ] = defaultdict(dict)
            consumer_model_evidence: dict[str, list[dict[str, object]]] = defaultdict(list)

            # Preserve multiple marketed variants from source model labels. This
            # recovers labels such as TrailSport and e:FCEV without promoting the
            # whole EPA configuration string to a separate model.
            for provider in ("nhtsa_vpic", "fueleconomy_gov"):
                for source_model in provider_labels.get(provider, []):
                    for variant in model_variants(model, source_model):
                        evidence = {
                            "status": "source_label",
                            "source_model": source_model,
                            "model_variant": variant,
                        }
                        trim_observations[legacy.normalized_key(variant)][provider] = (
                            variant,
                            evidence,
                        )

            for source_model in v2._source_model_aliases(model, provider_labels):
                for provider, fetcher in (
                    ("kbb", legacy._kbb_trims),
                    ("carsdirect", legacy._carsdirect_trims),
                ):
                    trims, evidence = await asyncio.to_thread(
                        fetcher,
                        make,
                        source_model,
                        year,
                        refresh,
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

                    variants = model_variants(model, source_model) or (None,)
                    canonical_trims: set[str] = set()
                    for trim in trims:
                        if (strict := _strict_trim_value(trim)) is None:
                            continue
                        for variant in variants:
                            combined = legacy.combine_trim_variant(strict, variant)
                            if combined is not None:
                                canonical_trims.add(combined)
                    if (
                        variants != (None,)
                        and not canonical_trims
                        and status in {"success", "cached"}
                    ):
                        canonical_trims.update(
                            variant
                            for variant in variants
                            if variant is not None
                        )

                    if canonical_trims:
                        enriched = dict(evidence)
                        enriched["source_model"] = source_model
                        if variants != (None,):
                            enriched["model_variants"] = [
                                variant for variant in variants if variant is not None
                            ]
                        consumer_model_evidence[provider].append(enriched)
                        for trim in canonical_trims:
                            key = legacy.normalized_key(trim)
                            trim_observations[key][provider] = (trim, enriched)

            trim_observations = _finalize_trim_observations(
                trim_observations,
                provider_labels,
            )

            has_fueleconomy = "fueleconomy_gov" in provider_labels
            has_consumer = bool(consumer_model_evidence)
            nhtsa_future_candidate = (
                year == legacy.US_IDENTITY_YEAR_MAX
                and "nhtsa_vpic" in provider_labels
            )
            if not (has_fueleconomy or has_consumer or nhtsa_future_candidate):
                unresolved_models.append(model)
                continue

            model_source_labels = {
                provider: list(labels)
                for provider, labels in provider_labels.items()
            }
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
                labels = [item[0] for item in provider_map.values()]
                canonical_label = min(
                    labels,
                    key=lambda value: (len(value), value.casefold()),
                )
                for provider, (_label, evidence) in provider_map.items():
                    await legacy._upsert_trim(
                        model_row,
                        canonical_label,
                        provider,
                        evidence,
                    )
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
                    "unresolved_source_only_models": sorted(
                        unresolved_models,
                        key=str.casefold,
                    ),
                    "unresolved_source_only_model_count": len(unresolved_models),
                    "identity_label_strategy": "marketed_selection_v3",
                }
                row.completed_at = legacy._now()

        print(
            f"PASS {year} {make}: {accepted_models} canonical models, "
            f"{len(unique_trim_keys)} marketed selection rows, "
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


async def export_json(path: str) -> None:
    async with legacy.session_factory() as session:
        models = list(
            await session.scalars(
                select(legacy.CatalogIdentityModel).order_by(
                    legacy.CatalogIdentityModel.make,
                    legacy.CatalogIdentityModel.year,
                    legacy.CatalogIdentityModel.model,
                )
            )
        )
        trims = list(
            await session.scalars(
                select(legacy.CatalogIdentityTrim).order_by(
                    legacy.CatalogIdentityTrim.trim
                )
            )
        )

    trims_by_model: dict[str, list[legacy.CatalogIdentityTrim]] = {}
    for trim in trims:
        trims_by_model.setdefault(str(trim.model_id), []).append(trim)

    payload: dict[str, object] = {
        "scope": {
            "market": legacy.US_IDENTITY_MARKET,
            "year_from": legacy.US_IDENTITY_YEAR_MIN,
            "year_to": legacy.US_IDENTITY_YEAR_MAX,
            "makes": list(legacy.US_IDENTITY_MAKES),
            "identity_label_strategy": "marketed_selection_v3",
        },
        "generated_at": legacy._now().isoformat(),
        "models": [
            {
                "year": model.year,
                "make": model.make,
                "model": model.model,
                "status": model.status,
                "source_count": model.source_count,
                "sources": model.sources,
                "trims": [
                    {
                        "trim": trim.trim,
                        "dimensions": identity_dimensions(trim.trim),
                        "status": trim.status,
                        "source_count": trim.source_count,
                        "sources": trim.sources,
                    }
                    for trim in trims_by_model.get(str(model.id), [])
                ],
            }
            for model in models
        ],
    }

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Exported {len(models)} model-year rows to {destination}")


def install_v3_behavior() -> None:
    v2.install_v2_behavior()

    # V2's collector resolves these names at run time, so the V3 entry point can
    # tighten parsing without duplicating or invalidating V2's source cache.
    v2.model_variant = model_variant
    legacy.model_variant = model_variant
    legacy.trim_from_kbb_style = trim_from_kbb_style
    legacy.trim_from_carsdirect_style = trim_from_carsdirect_style
    legacy.extract_kbb_trims = extract_kbb_trims
    legacy.extract_carsdirect_trims = extract_carsdirect_trims
    legacy.collect_make_year = _collect_make_year
    legacy.export_json = export_json


def main() -> None:
    install_v3_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
