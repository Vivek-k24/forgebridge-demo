#!/usr/bin/env python3
"""Collect candidate drivetrain catalog observations for the 6th-gen Honda Civic.

This is a generation-level orchestrator around the deterministic collector introduced
in PR #15. It deliberately keeps the same trust boundary: public catalog pages are
candidate fitment/identity evidence only and are never promoted to mechanical/service
truth automatically.

Scope
-----
Honda Civic model years 1996-2000. "Drivetrain" here means transmission/transaxle,
clutch/torque-converter, final-drive/differential, drive-shaft/axle/CV components,
engine/transmission mounts, and shift/selector mechanisms. Engine internals, cooling,
fuel, exhaust, brakes, suspension, steering, A/C, body, and safety systems are outside
this collection.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterable, Sequence

from build_honda_parts_catalog import (
    CATALOG_YEARS,
    DEFAULT_CACHE,
    DEFAULT_DB,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_SCHEMA,
    AssemblyPage,
    Fetcher,
    VehicleConfig,
    discover_assembly_pages,
    extract_part_candidates,
    open_database,
    stable_id,
    store_candidate,
    upsert_assembly,
    upsert_source,
    upsert_vehicle,
    utc_now,
)

ROOT = Path(__file__).resolve().parents[1]
CIVIC_SIXTH_GEN_YEARS = (1996, 1997, 1998, 1999, 2000)
DEFAULT_SUMMARY = ROOT / "data" / "catalog" / "civic-6th-gen-drivetrain-summary.json"

# Matching is intentionally based only on source catalog assembly metadata. The
# collector does not infer that a part belongs to the drivetrain from a seller name.
DEFAULT_DRIVETRAIN_TERMS = (
    "transmission",
    "transaxle",
    "clutch",
    "flywheel",
    "torque converter",
    "torque_converter",
    "differential",
    "final drive",
    "final_drive",
    "drive shaft",
    "drive_shaft",
    "driveshaft",
    "half shaft",
    "half_shaft",
    "axle shaft",
    "axle_shaft",
    "intermediate shaft",
    "intermediate_shaft",
    "cv joint",
    "cv_joint",
    "constant velocity",
    "engine mount",
    "engine_mount",
    "transmission mount",
    "transmission_mount",
    "shift lever",
    "shift_lever",
    "shift cable",
    "shift_cable",
    "shift linkage",
    "shift_linkage",
    "selector lever",
    "selector_lever",
    "mainshaft",
    "countershaft",
)


def assembly_search_text(assembly: AssemblyPage) -> str:
    return " ".join(
        (
            assembly.category_slug,
            assembly.category_label,
            assembly.assembly_slug,
            assembly.assembly_label,
            assembly.url,
        )
    ).casefold()


def is_drivetrain_assembly(assembly: AssemblyPage, terms: Sequence[str]) -> bool:
    searchable = assembly_search_text(assembly)
    return any(term.casefold() in searchable for term in terms)


def fetch_with_retries(
    fetcher: Fetcher,
    url: str,
    retries: int,
    retry_backoff: float,
    label: str,
) -> tuple[str, bool]:
    """Retry transient catalog failures without weakening PR #15's robots/rate limits."""
    attempts = max(1, retries + 1)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fetcher.fetch_text(url)
        except Exception as exc:  # the PR #15 fetcher normalizes network/HTTP failures
            last_error = exc
            if attempt >= attempts:
                break
            sleep_seconds = max(0.0, retry_backoff) * attempt
            print(
                f"[generation] retry {attempt}/{retries} for {label} after {exc}; "
                f"sleeping {sleep_seconds:.1f}s",
                file=sys.stderr,
            )
            if sleep_seconds:
                time.sleep(sleep_seconds)
    assert last_error is not None
    raise last_error


def load_civic_configs(years: Iterable[int], model: str) -> list[VehicleConfig]:
    model_normalized = model.casefold().strip()
    vehicles: list[VehicleConfig] = []
    seen_keys: set[str] = set()

    for year in sorted(set(years)):
        if year not in CIVIC_SIXTH_GEN_YEARS:
            raise RuntimeError(
                f"{year} is outside the staged 6th-generation Civic range "
                f"{CIVIC_SIXTH_GEN_YEARS[0]}-{CIVIC_SIXTH_GEN_YEARS[-1]}."
            )
        path = CATALOG_YEARS / f"{year}.json"
        if not path.exists():
            raise RuntimeError(f"Vehicle catalog file is missing: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("records", []):
            if str(item.get("model", "")).casefold().strip() != model_normalized:
                continue
            key = str(item.get("key", "")).strip()
            source_url = str(item.get("sourceUrl", "")).strip()
            if not key or not source_url or key in seen_keys:
                continue
            seen_keys.add(key)
            vehicles.append(
                VehicleConfig(
                    key=key,
                    year=int(item["year"]),
                    model=str(item["model"]),
                    body_trim=str(item.get("bodyTrim", "")),
                    emission_transmission=str(item.get("emissionTransmission", "")),
                    source_url=source_url,
                    market=str(item.get("market", "catalog-coded")),
                )
            )

    return sorted(vehicles, key=lambda item: (item.year, item.key))


def database_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "vehicle_configs",
        "assemblies",
        "parts",
        "part_fitment_observations",
        "assembly_part_observations",
        "part_media_refs",
        "catalog_scrape_runs",
    )
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def collect(args: argparse.Namespace) -> int:
    years = tuple(args.year or CIVIC_SIXTH_GEN_YEARS)
    terms = tuple(args.assembly_term or DEFAULT_DRIVETRAIN_TERMS)
    vehicles = load_civic_configs(years, args.model)
    if args.max_configs is not None:
        vehicles = vehicles[: args.max_configs]
    if not vehicles:
        raise RuntimeError("No exact Civic configurations matched the requested generation/year scope.")

    db_path = Path(args.db)
    summary_path = Path(args.summary)
    fetcher = Fetcher(Path(args.cache_dir), args.delay, args.refresh, args.offline)
    connection = open_database(db_path, Path(args.schema))

    totals = {
        "vehicle_configs_requested": len(vehicles),
        "vehicle_configs_with_drivetrain_pages": 0,
        "vehicle_page_errors": 0,
        "assembly_pages_discovered": 0,
        "drivetrain_assembly_pages_matched": 0,
        "drivetrain_assembly_pages_stored": 0,
        "part_observations_stored": 0,
        "assembly_errors": 0,
        "cache_hits": 0,
    }
    vehicle_results: list[dict[str, object]] = []

    try:
        for vehicle_position, vehicle in enumerate(vehicles, start=1):
            print(
                f"[generation] vehicle {vehicle_position}/{len(vehicles)}: "
                f"{vehicle.key} ({vehicle.body_trim} · {vehicle.emission_transmission})",
                file=sys.stderr,
            )
            upsert_vehicle(connection, vehicle)
            result: dict[str, object] = {
                "key": vehicle.key,
                "year": vehicle.year,
                "bodyTrim": vehicle.body_trim,
                "emissionTransmission": vehicle.emission_transmission,
                "sourceUrl": vehicle.source_url,
                "discoveredAssemblies": 0,
                "matchedDrivetrainAssemblies": 0,
                "storedAssemblies": 0,
                "storedPartObservations": 0,
                "errors": [],
            }

            try:
                vehicle_html, vehicle_cache_hit = fetch_with_retries(
                    fetcher,
                    vehicle.source_url,
                    args.retries,
                    args.retry_backoff,
                    f"vehicle {vehicle.key}",
                )
                totals["cache_hits"] += int(vehicle_cache_hit)
                assemblies = discover_assembly_pages(vehicle.source_url, vehicle_html)
                result["discoveredAssemblies"] = len(assemblies)
                totals["assembly_pages_discovered"] += len(assemblies)
            except Exception as exc:  # keep the generation run appendable/resumable
                totals["vehicle_page_errors"] += 1
                result["errors"].append(f"vehicle page: {exc}")
                vehicle_results.append(result)
                connection.commit()
                print(f"[generation] vehicle skipped after retries: {exc}", file=sys.stderr)
                if args.fail_fast:
                    raise
                continue

            drivetrain_assemblies = [
                assembly for assembly in assemblies if is_drivetrain_assembly(assembly, terms)
            ]
            if args.max_assemblies_per_config is not None:
                drivetrain_assemblies = drivetrain_assemblies[: args.max_assemblies_per_config]
            result["matchedDrivetrainAssemblies"] = len(drivetrain_assemblies)
            totals["drivetrain_assembly_pages_matched"] += len(drivetrain_assemblies)
            if drivetrain_assemblies:
                totals["vehicle_configs_with_drivetrain_pages"] += 1

            for assembly_position, assembly in enumerate(drivetrain_assemblies, start=1):
                print(
                    f"[generation]   {assembly_position}/{len(drivetrain_assemblies)} "
                    f"{assembly.category_label} / {assembly.assembly_label}",
                    file=sys.stderr,
                )
                source_id = upsert_source(
                    connection,
                    assembly.url,
                    vehicle.market,
                    "Public catalog candidate evidence only; not American Honda OEM authority and not repair/service truth.",
                )
                started_at = utc_now()
                run_id = stable_id(
                    "run",
                    source_id,
                    vehicle.key,
                    started_at,
                    assembly_position,
                )
                try:
                    page_html, cache_hit = fetch_with_retries(
                        fetcher,
                        assembly.url,
                        args.retries,
                        args.retry_backoff,
                        assembly.url,
                    )
                    totals["cache_hits"] += int(cache_hit)
                    candidates = extract_part_candidates(assembly.url, page_html)
                    assembly_id = upsert_assembly(connection, vehicle, assembly, source_id)
                    for candidate in candidates:
                        store_candidate(connection, vehicle, assembly_id, source_id, candidate)
                    connection.execute(
                        """
                        INSERT INTO catalog_scrape_runs (
                          id, started_at, finished_at, source_id, http_status,
                          robots_allowed, extracted_part_count, error_text
                        ) VALUES (?, ?, ?, ?, 200, 1, ?, NULL)
                        """,
                        (run_id, started_at, utc_now(), source_id, len(candidates)),
                    )
                    totals["drivetrain_assembly_pages_stored"] += 1
                    totals["part_observations_stored"] += len(candidates)
                    result["storedAssemblies"] = int(result["storedAssemblies"]) + 1
                    result["storedPartObservations"] = int(result["storedPartObservations"]) + len(candidates)
                    connection.commit()
                except Exception as exc:  # preserve PR #15 provenance for unresolved failures
                    totals["assembly_errors"] += 1
                    result["errors"].append(f"{assembly.url}: {exc}")
                    connection.execute(
                        """
                        INSERT INTO catalog_scrape_runs (
                          id, started_at, finished_at, source_id, http_status,
                          robots_allowed, extracted_part_count, error_text
                        ) VALUES (?, ?, ?, ?, NULL, 0, 0, ?)
                        """,
                        (run_id, started_at, utc_now(), source_id, str(exc)[:1000]),
                    )
                    connection.commit()
                    print(f"[generation]   skipped after retries: {exc}", file=sys.stderr)
                    if args.fail_fast:
                        raise

            vehicle_results.append(result)
            connection.commit()

        counts = database_counts(connection)
        summary = {
            "collector": "scripts/build_honda_parts_catalog.py (PR #15 core)",
            "scope": {
                "make": "Honda",
                "model": args.model,
                "generation": 6,
                "years": list(years),
                "definition": (
                    "Transmission/transaxle, clutch/torque-converter, final-drive/differential, "
                    "drive-shaft/axle/CV, engine/transmission mounts, and shift/selector catalog assemblies."
                ),
                "excluded": (
                    "Engine internals, cooling, fuel, exhaust, brakes, suspension, steering, A/C, body, and safety."
                ),
                "assemblyMatchTerms": list(terms),
            },
            "trustBoundary": (
                "All collected rows remain candidate catalog observations with source provenance; "
                "they are not automatically verified mechanical/service facts."
            ),
            "database": str(db_path),
            "cacheDirectory": str(Path(args.cache_dir)),
            "totals": totals,
            "databaseCounts": counts,
            "vehicles": vehicle_results,
            "finishedAt": utc_now(),
        }
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        print(json.dumps({"totals": totals, "databaseCounts": counts}, indent=2), file=sys.stderr)
        print(db_path.resolve())
        print(summary_path.resolve())

        complete = (
            totals["drivetrain_assembly_pages_stored"] > 0
            and totals["vehicle_page_errors"] == 0
            and totals["assembly_errors"] == 0
            and totals["drivetrain_assembly_pages_stored"] == totals["drivetrain_assembly_pages_matched"]
        )
        if not complete:
            print(
                "[generation] incomplete collection: unresolved source-page errors remain; "
                "the workflow must not merge this shard as complete.",
                file=sys.stderr,
            )
        return 0 if complete else 2
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect candidate drivetrain catalog observations for 1996-2000 Honda Civic configurations."
    )
    parser.add_argument(
        "--year",
        type=int,
        action="append",
        help="Model year to collect. Repeat for multiple years; defaults to 1996-2000.",
    )
    parser.add_argument("--model", default="Civic", help="Honda model name; defaults to Civic")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite output path")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Catalog schema path")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY), help="JSON run-summary output path")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE), help="Local uncommitted HTTP cache")
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="Minimum seconds between network page requests",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retries after a transient vehicle/assembly fetch failure (default: 3)",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=2.0,
        help="Linear retry backoff in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--assembly-term",
        action="append",
        help="Override the default drivetrain assembly match terms; repeat for multiple terms",
    )
    parser.add_argument("--refresh", action="store_true", help="Ignore cached HTML and fetch again")
    parser.add_argument("--offline", action="store_true", help="Use cache only; make no network requests")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on the first unresolved retrieval/parse error")
    parser.add_argument(
        "--max-configs",
        type=int,
        default=None,
        help="Safety/testing cap on exact configurations",
    )
    parser.add_argument(
        "--max-assemblies-per-config",
        type=int,
        default=None,
        help="Safety/testing cap on matched drivetrain assembly pages per exact configuration",
    )
    return parser


def main() -> int:
    return collect(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
