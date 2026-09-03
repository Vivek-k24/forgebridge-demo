"""Command-line entry point for raw catalog collection.

Examples:
    python -m partgraph.collectors.cli trims \
        --year 2012 --make Honda --model Civic --category-id 33707

    python -m partgraph.collectors.cli inventory \
        --query "brake pads" --category-id 33559 \
        --year 2012 --make Honda --model Civic \
        --trim "EX Sedan 4-Door" \
        --engine "1.8L 1799CC l4 GAS SOHC Naturally Aspirated"
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Iterable

from ..database import session_factory
from .ebay import CollectedObservation, EbayCatalogClient, VehicleApplication
from .staging import finish_ingestion_batch, stage_observation, start_ingestion_batch

COLLECTOR_VERSION = "ebay-v1"


async def _persist(
    observations: Iterable[CollectedObservation],
    *,
    source_name: str,
) -> int:
    async with session_factory() as session:
        batch = await start_ingestion_batch(
            session,
            source_name=source_name,
            source_type="retailer",
            collector_version=COLLECTOR_VERSION,
        )
        await session.commit()
        count = 0
        try:
            for observation in observations:
                await stage_observation(
                    session,
                    batch=batch,
                    source_record_id=observation.source_record_id,
                    source_url=observation.source_url,
                    candidate_type=observation.candidate_type,
                    raw_payload=observation.raw_payload,
                    candidate_payload=observation.candidate_payload,
                    vehicle_identity=observation.vehicle_identity,
                    provenance=observation.provenance,
                    extraction_method=observation.extraction_method,
                )
                count += 1
            await finish_ingestion_batch(session, batch)
            await session.commit()
            return count
        except Exception:
            await session.rollback()
            batch.status = "failed"
            await finish_ingestion_batch(session, batch, status="failed")
            await session.commit()
            raise


async def _run(args: argparse.Namespace) -> int:
    client = EbayCatalogClient()
    if args.command == "trims":
        observations = client.trim_observations(
            category_id=args.category_id,
            year=args.year,
            make=args.make,
            model=args.model,
        )
        count = await _persist(observations, source_name="ebay_motors_metadata")
        print(f"staged {count} trim/engine candidates")
        return 0

    vehicle = VehicleApplication(
        year=args.year,
        make=args.make,
        model=args.model,
        trim=args.trim,
        engine=args.engine,
    )
    observations = client.inventory_observations(
        query=args.query,
        category_id=args.category_id,
        vehicle=vehicle,
        limit=args.limit,
    )
    count = await _persist(observations, source_name="ebay_motors_browse")
    print(f"staged {count} inventory/part/fitment observations")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect raw PartGraph catalog observations")
    commands = parser.add_subparsers(dest="command", required=True)

    trims = commands.add_parser("trims", help="collect trim and engine taxonomy candidates")
    trims.add_argument("--year", type=int, required=True)
    trims.add_argument("--make", required=True)
    trims.add_argument("--model", required=True)
    trims.add_argument("--category-id", required=True)

    inventory = commands.add_parser(
        "inventory", help="collect live parts, inventory, and fitment candidates"
    )
    inventory.add_argument("--query", required=True)
    inventory.add_argument("--year", type=int, required=True)
    inventory.add_argument("--make", required=True)
    inventory.add_argument("--model", required=True)
    inventory.add_argument("--trim")
    inventory.add_argument("--engine")
    inventory.add_argument("--category-id", required=True)
    inventory.add_argument("--limit", type=int, default=50)
    return parser


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
