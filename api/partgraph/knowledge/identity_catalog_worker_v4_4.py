from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy import select

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v2 as v2
from . import identity_catalog_worker_v3 as v3
from . import identity_catalog_worker_v4 as v4
from . import identity_catalog_worker_v4_3 as v4_3

# V4.4 is the final identity-coverage reconciliation pass for the six-make
# catalog. It does two things that the automated V4.3 pass could not do safely:
#
# 1. When a normal KBB model page yields no marketed selections, it tries the
#    public KBB /specs/ page and keeps the same raw-cache/provenance rules.
# 2. It applies a very small set of source-backed identity supplements that were
#    verified against manufacturer/KBB/Edmunds pages during the final audit.
#
# No engine, transmission, horsepower, drivetrain, part, fluid, or procedure
# facts are collected here. This remains year + make + model + trim only.

_BASE_KBB_TRIMS = legacy._kbb_trims
_BASE_COLLECT_MAKE_YEAR = v3._collect_make_year
_V4_MODEL_VARIANTS = v4.model_variants

_HYBRID_TOKEN_RE = re.compile(r"\b(?:hybrid|hev)\b", re.I)


def model_variants(canonical_model: str, source_model: str) -> tuple[str, ...]:
    """Keep Hybrid attached to a marketed grade encoded in a source model label."""

    remainder = v3._remove_model_family(canonical_model, source_model)
    if _HYBRID_TOKEN_RE.search(remainder):
        if "/" in remainder:
            return _V4_MODEL_VARIANTS(canonical_model, source_model)

        without_hybrid = _HYBRID_TOKEN_RE.sub(" ", remainder)
        variant = v3._marketed_variant_from_text(without_hybrid)
        if variant is not None:
            return (f"{variant} Hybrid",)
        return ("Hybrid",)

    return _V4_MODEL_VARIANTS(canonical_model, source_model)


def model_variant(canonical_model: str, source_model: str) -> str | None:
    variants = model_variants(canonical_model, source_model)
    return variants[0] if variants else None


def _recover_base_from_family_echo(trims: list[str], source_model: str) -> list[str]:
    """Turn an explicit unbadged KBB style row into the conventional Base grade.

    KBB often names the entry-level style only as the model plus its body style,
    e.g. "Outback Wagon 4D", "Forester Sport Utility 4D", or
    "Land Cruiser Sport Utility 4D". V4.3 correctly rejected a bare model echo,
    but that also hid the real unbadged/base selection. We recover Base only
    when the source actually exposed that family echo as a style row.
    """

    recovered = list(trims)
    source_key = legacy.normalized_key(source_model)
    for label in trims:
        _body, grade = v3._split_body_prefix(label)
        grade = grade or label
        if legacy.normalized_key(grade) == source_key:
            recovered.append("Base")
            break
    return sorted(dict.fromkeys(recovered), key=str.casefold)


def _kbb_trims(
    make: str,
    source_model: str,
    year: int,
    refresh: bool,
) -> tuple[list[str], dict[str, object]]:
    """Use the normal KBB page first, then /specs/ only when coverage is empty."""

    trims, evidence = _BASE_KBB_TRIMS(make, source_model, year, refresh)
    trims = _recover_base_from_family_echo(trims, source_model)
    if trims:
        return trims, evidence

    # A hard network failure on the primary request retains the existing V3
    # fail-closed behavior. /specs/ is a coverage fallback, not an error bypass.
    if evidence.get("status") == "failed":
        return trims, evidence

    url = f"https://www.kbb.com/{legacy.slug(make)}/{legacy.slug(source_model)}/{year}/specs/"
    raw, specs_evidence = legacy._fetch_cached(
        "kbb",
        make,
        year,
        url,
        accept="text/html,application/xhtml+xml;q=0.9",
        suffix="html",
        refresh=refresh,
    )
    if raw is None:
        enriched = dict(evidence)
        enriched["specs_fallback"] = specs_evidence
        return trims, enriched

    specs_trims = legacy.extract_kbb_trims(raw, make, source_model, year)
    specs_trims = _recover_base_from_family_echo(specs_trims, source_model)
    if not specs_trims:
        enriched = dict(evidence)
        enriched["specs_fallback"] = specs_evidence
        return trims, enriched

    enriched = dict(specs_evidence)
    enriched["recovery_path"] = "kbb_specs"
    enriched["primary_capture"] = evidence
    return specs_trims, enriched


# Each row below was checked against a public consumer/manufacturer source in the
# final September 6, 2026 audit. These are not guesses and do not stand in for a
# general hardcoded vehicle database. They cover known gaps where the automated
# providers either omit a marketed selection or present it as a package/body
# configuration that cannot be safely inferred by generic parsing.
_SOURCE_BACKED_SUPPLEMENTS: dict[
    tuple[str, int, str],
    tuple[str, tuple[tuple[str, str], ...]],
] = {
    (
        "Honda",
        2026,
        "Civic",
    ): (
        "official_honda",
        (
            (
                "Sedan Sport Hybrid",
                "https://automobiles.honda.com/2026/civic-sedan/specs-features-trim-comparison",
            ),
            (
                "Sedan Sport Touring Hybrid",
                "https://automobiles.honda.com/2026/civic-sedan/specs-features-trim-comparison",
            ),
            (
                "Hatchback Sport Hybrid",
                "https://automobiles.honda.com/2026/civic-hatchback/specs-features-trim-comparison",
            ),
            (
                "Hatchback Sport Touring Hybrid",
                "https://automobiles.honda.com/2026/civic-hatchback/specs-features-trim-comparison",
            ),
        ),
    ),
    (
        "Honda",
        2026,
        "CR-V",
    ): (
        "official_honda",
        (
            (
                "Sport Hybrid",
                "https://automobiles.honda.com/2026/cr-v/specs-features-trim-comparison",
            ),
            (
                "TrailSport Hybrid",
                "https://automobiles.honda.com/2026/cr-v/specs-features-trim-comparison",
            ),
            (
                "Sport-L Hybrid",
                "https://automobiles.honda.com/2026/cr-v/specs-features-trim-comparison",
            ),
            (
                "Sport Touring Hybrid",
                "https://automobiles.honda.com/2026/cr-v/specs-features-trim-comparison",
            ),
        ),
    ),
    (
        "Honda",
        2026,
        "Pilot",
    ): (
        "official_honda",
        (
            (
                "Touring Blackout",
                "https://automobiles.honda.com/pilot/specs-features-trim-comparison",
            ),
        ),
    ),
    (
        "Honda",
        2026,
        "Prelude",
    ): (
        "official_honda",
        (
            ("Hybrid", "https://automobiles.honda.com/2026/prelude"),
            ("Hybrid Two-Tone", "https://automobiles.honda.com/2026/prelude"),
        ),
    ),
    (
        "Honda",
        2027,
        "CR-V",
    ): (
        "official_honda",
        tuple(
            (trim, "https://automobiles.honda.com/cr-v/specs-features-trim-comparison")
            for trim in (
                "LX",
                "EX",
                "EX-L",
                "Sport Hybrid",
                "TrailSport Hybrid",
                "Sport-L Hybrid",
                "Sport Touring Hybrid",
            )
        ),
    ),
    (
        "Honda",
        2027,
        "HR-V",
    ): (
        "official_honda",
        tuple(
            (trim, "https://automobiles.honda.com/hr-v/specs-features-trim-comparison")
            for trim in ("LX", "Sport", "EX-L")
        ),
    ),
    (
        "Honda",
        2027,
        "Odyssey",
    ): (
        "official_honda",
        tuple(
            (trim, "https://automobiles.honda.com/odyssey/specs-features-trim-comparison")
            for trim in ("EX-L", "Sport-L", "Touring", "Elite")
        ),
    ),
    (
        "Honda",
        2027,
        "Prelude",
    ): (
        "official_honda",
        (
            ("Hybrid", "https://automobiles.honda.com/prelude/specs-features-trim-comparison"),
            (
                "Hybrid Two-Tone",
                "https://automobiles.honda.com/prelude/specs-features-trim-comparison",
            ),
        ),
    ),
    (
        "Toyota",
        2018,
        "Land Cruiser",
    ): (
        "toyota_newsroom",
        (
            (
                "Base",
                "https://pressroom.toyota.com/2018-toyota-land-cruiser-full-capability-luxury/",
            ),
        ),
    ),
    (
        "Lexus",
        2019,
        "GX",
    ): (
        "lexus_newsroom",
        (
            ("460 Premium", "https://pressroom.lexus.com/2019-lexus-gx-460-press-kit/"),
        ),
    ),
    (
        "Lexus",
        2019,
        "IS",
    ): (
        "lexus_official",
        (
            (
                "300 F SPORT",
                "https://www.lexus.com/content/dam/lexus/documents/brochures/models/2019/MY19-Lexus-IS-Brochure.pdf",
            ),
            (
                "350 F SPORT",
                "https://www.lexus.com/content/dam/lexus/documents/brochures/models/2019/MY19-Lexus-IS-Brochure.pdf",
            ),
        ),
    ),
    (
        "Lexus",
        2019,
        "LX",
    ): (
        "lexus_official",
        (
            (
                "570 Two-Row",
                "https://www.lexus.com/content/dam/lexus/documents/brochures/models/2019/MY19-Lexus-LX-Brochure.pdf",
            ),
            (
                "570 Three-Row",
                "https://www.lexus.com/content/dam/lexus/documents/brochures/models/2019/MY19-Lexus-LX-Brochure.pdf",
            ),
        ),
    ),
    (
        "Subaru",
        2024,
        "Outback",
    ): (
        "kbb_specs_reference",
        (("Base", "https://www.kbb.com/subaru/outback/2024/specs/"),),
    ),
    (
        "Subaru",
        2023,
        "Forester",
    ): (
        "kbb_specs_reference",
        (("Base", "https://www.kbb.com/subaru/forester/2023/specs/"),),
    ),
    (
        "Subaru",
        2023,
        "Ascent",
    ): (
        "kbb_specs_reference",
        (("Base", "https://www.kbb.com/subaru/ascent/2023/specs/"),),
    ),
    (
        "Subaru",
        2007,
        "Legacy",
    ): (
        "edmunds_reference",
        (
            (
                "Sedan 2.5i Special Edition",
                "https://www.edmunds.com/subaru/legacy/2007/review/",
            ),
            (
                "Wagon 2.5i Special Edition",
                "https://www.edmunds.com/subaru/legacy/2007/review/",
            ),
        ),
    ),
}

# Remove only labels for which the final audit found an exact, source-backed
# replacement. This list deliberately stays tiny.
_REPLACED_LABELS: dict[tuple[str, int, str], set[str]] = {
    ("Honda", 2026, "CR-V"): {"TrailSport"},
    ("Honda", 2026, "Prelude"): {"Base"},
    ("Honda", 2027, "Prelude"): {"Base", "2-Tone Hybrid"},
    ("Lexus", 2019, "LX"): {"570"},
}


async def _model_row(make: str, year: int, model: str):
    async with legacy.session_factory() as session:
        return await session.scalar(
            select(legacy.CatalogIdentityModel).where(
                legacy.CatalogIdentityModel.market == legacy.US_IDENTITY_MARKET,
                legacy.CatalogIdentityModel.year == year,
                legacy.CatalogIdentityModel.make_key == legacy.normalized_key(make),
                legacy.CatalogIdentityModel.model_key == legacy.normalized_key(model),
            )
        )


async def _apply_source_backed_supplements(make: str, year: int) -> None:
    for (row_make, row_year, model), (provider, rows) in _SOURCE_BACKED_SUPPLEMENTS.items():
        if row_make != make or row_year != year:
            continue

        model_row = await _model_row(make, year, model)
        if model_row is None:
            # Supplements never manufacture a model family. The broad model must
            # already have been accepted by the normal NHTSA/FuelEconomy/consumer
            # collection path.
            continue

        drop_labels = _REPLACED_LABELS.get((make, year, model), set())
        if drop_labels:
            drop_keys = [legacy.normalized_key(value) for value in drop_labels]
            async with legacy.session_factory() as session:
                async with session.begin():
                    await session.execute(
                        legacy.delete(legacy.CatalogIdentityTrim).where(
                            legacy.CatalogIdentityTrim.model_id == model_row.id,
                            legacy.CatalogIdentityTrim.trim_key.in_(drop_keys),
                        )
                    )

        captures: list[dict[str, object]] = []
        for trim, url in rows:
            evidence = {
                "status": "source_backed_audit",
                "url": url,
                "source_model": model,
                "audit_date": "2026-09-06",
                "identity_only": True,
            }
            captures.append(evidence)
            await legacy._upsert_trim(model_row, trim, provider, evidence)

        # The same evidence also corroborates that this exact model-year exists.
        async with legacy.session_factory() as session:
            async with session.begin():
                persisted = await session.get(legacy.CatalogIdentityModel, model_row.id)
                if persisted is not None:
                    merged = dict(persisted.sources)
                    merged[provider] = {
                        "labels": [model],
                        "capture": {
                            "status": "source_backed_audit",
                            "captures": captures,
                        },
                    }
                    persisted.sources = merged
                    persisted.source_count = len(merged)
                    persisted.status = "corroborated" if len(merged) >= 2 else "discovered"


async def collect_make_year(make: str, year: int, *, refresh: bool) -> None:
    await _BASE_COLLECT_MAKE_YEAR(make, year, refresh=refresh)
    await _apply_source_backed_supplements(make, year)


async def export_json(path: str) -> None:
    await v4_3.export_json(path)
    destination = Path(path)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload.setdefault("scope", {})["identity_label_strategy"] = "marketed_selection_v4_4"

    supplemented = 0
    kbb_specs_recovered = 0
    for model in payload.get("models", []):
        if not isinstance(model, dict):
            continue
        for trim in model.get("trims", []):
            if not isinstance(trim, dict):
                continue
            sources = trim.get("sources", {})
            if any(
                provider in sources
                for provider in (
                    "official_honda",
                    "toyota_newsroom",
                    "lexus_newsroom",
                    "lexus_official",
                    "kbb_specs_reference",
                    "edmunds_reference",
                )
            ):
                supplemented += 1
            kbb = sources.get("kbb") if isinstance(sources, dict) else None
            if isinstance(kbb, dict) and kbb.get("recovery_path") == "kbb_specs":
                kbb_specs_recovered += 1

    quality = payload.setdefault("quality_summary", {})
    quality["source_backed_audit_selection_rows"] = supplemented
    quality["kbb_specs_recovered_selection_rows"] = kbb_specs_recovered
    destination.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")


def install_v4_4_behavior() -> None:
    v4_3.install_v4_3_behavior()

    # Exact-year hybrid grade reconciliation must be visible to both the V3
    # collector and V4 alias builder.
    v3.model_variants = model_variants
    v3.model_variant = model_variant
    v4.model_variants = model_variants
    v4.model_variant = model_variant
    legacy.model_variant = model_variant

    legacy._kbb_trims = _kbb_trims
    legacy.collect_make_year = collect_make_year
    legacy.export_json = export_json


def main() -> None:
    install_v4_4_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
