from __future__ import annotations

import asyncio
from collections import defaultdict

from sqlalchemy import select

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v2 as v2
from . import identity_catalog_worker_v3 as v3
from . import identity_catalog_worker_v4 as v4
from . import identity_catalog_worker_v4_1 as v4_1

# V4.2 keeps V4.1's persisted-key/body-prefix fixes, activates the exact-year
# reconciliation in V4, and tightens the provenance boundary around successful
# consumer-page fetches and provisional 2027 NHTSA-only candidates.


async def _has_prior_canonical_family(make: str, year: int, model: str) -> bool:
    """Allow NHTSA-only future rows only for an already-observed consumer family."""

    if year != legacy.US_IDENTITY_YEAR_MAX:
        return False
    async with legacy.session_factory() as session:
        row = await session.scalar(
            select(legacy.CatalogIdentityModel.id)
            .where(
                legacy.CatalogIdentityModel.market == legacy.US_IDENTITY_MARKET,
                legacy.CatalogIdentityModel.make_key == legacy.normalized_key(make),
                legacy.CatalogIdentityModel.model_key == legacy.normalized_key(model),
                legacy.CatalogIdentityModel.year < year,
            )
            .limit(1)
        )
    return row is not None


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
                            legacy.CatalogIdentityModel.make_key
                            == legacy.normalized_key(make),
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

            # Source-model labels are direct identity evidence. Preserve their
            # conservative marketed variants even when a consumer site cannot
            # parse a trim page for the same alias.
            for provider in ("nhtsa_vpic", "fueleconomy_gov"):
                for source_model in provider_labels.get(provider, []):
                    for variant in v3.model_variants(model, source_model):
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

                    variants = v3.model_variants(model, source_model) or (None,)
                    canonical_trims: set[str] = set()
                    for trim in trims:
                        if (strict := v3._strict_trim_value(trim)) is None:
                            continue
                        for variant in variants:
                            combined = legacy.combine_trim_variant(strict, variant)
                            if combined is not None:
                                canonical_trims.add(combined)

                    # A 200/cached page with zero parsed trim labels is not trim
                    # evidence. V3 previously promoted the alias variant solely
                    # from page reachability, which let redirects/generic pages
                    # fabricate Hybrid rows. Direct NHTSA/FuelEconomy variants
                    # above remain intact, so no source-backed identity is lost.
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

            trim_observations = v3._finalize_trim_observations(
                trim_observations,
                provider_labels,
            )

            has_fueleconomy = "fueleconomy_gov" in provider_labels
            has_consumer = bool(consumer_model_evidence)
            nhtsa_future_candidate = (
                year == legacy.US_IDENTITY_YEAR_MAX
                and "nhtsa_vpic" in provider_labels
                and await _has_prior_canonical_family(make, year, model)
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
                    "identity_label_strategy": "marketed_selection_v4_2",
                    "future_nhtsa_policy": (
                        "NHTSA-only 2027 rows require a prior canonical family; "
                        "brand-new source-only names remain unresolved until another "
                        "consumer/US-market source corroborates them"
                    ),
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


def install_v4_2_behavior() -> None:
    v4_1.install_v4_1_behavior()
    legacy.collect_make_year = _collect_make_year
    legacy.export_json = v4.export_json


def main() -> None:
    install_v4_2_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
