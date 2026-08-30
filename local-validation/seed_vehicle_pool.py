from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from partgraph.database import session_factory
from partgraph.vehicle.schemas import VehicleConfigurationInput
from partgraph.vehicle.service import resolve_configuration


async def seed() -> int:
    path = Path(__file__).with_name("vehicle_pool.json")
    vehicles = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(vehicles, list) or not vehicles:
        print("RESULT: FAIL — vehicle_pool.json is empty or invalid.")
        return 1

    counts: dict[str, int] = {}
    async with session_factory() as db:
        for raw in vehicles:
            payload = VehicleConfigurationInput.model_validate(raw)
            configuration, result = await resolve_configuration(db, payload)
            counts[result] = counts.get(result, 0) + 1
            if configuration.make != raw["make"]:
                print(
                    "RESULT: FAIL — canonical make mismatch for "
                    f"{raw['year']} {raw['make']} {raw['model']}."
                )
                return 1

    makes = {str(vehicle["make"]) for vehicle in vehicles}
    print(
        "RESULT: PASS — seeded "
        f"{len(vehicles)} synthetic canonical vehicle configurations across {len(makes)} makes."
    )
    print("Seed outcomes: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(seed()))
