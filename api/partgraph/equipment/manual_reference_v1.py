from __future__ import annotations

from collections.abc import Iterable

# Generic equipment terms used by the current PartGraph repair reference. These
# are search aliases, not vehicle-specific mechanical truth. Combined reference
# phrases intentionally point at multiple catalog rows when they describe more
# than one physical item (for example, a jack and jack stands).
REFERENCE_BASE_KEYWORDS: dict[str, str] = {
    "2-ton-hydraulic-floor-jack": "vehicle lifting jack",
    "2-ton-jack-stand-pair": "vehicle support stands",
    "rubber-wheel-chock-pair": "lifting support shop",
    "metal-wheel-chock-pair": "lifting support shop",
    "1-2-in-drive-19-mm-standard-socket": "metric socket six point",
    "3-8-in-drive-19-mm-standard-socket": "metric socket six point",
    "1-2-in-drive-torque-wrench": "socket wrench handle",
    "1-4-in-drive-torque-wrench": "socket wrench handle",
    "brake-caliper-piston-compressor": "automotive mechanic specialty tool",
    "coolant-funnel-kit": "fluid oil coolant brake service",
    "spill-free-coolant-funnel": "fluid oil coolant brake service",
    "hose-clamp-pliers": "hand plier cutter gripping",
    "safety-glasses-clear": "shop safety protection equipment",
    "mechanic-gloves-nitrile-coated": "shop safety protection equipment",
    "3-8-in-drive-14-mm-standard-socket": "metric socket six point",
    "14-mm-open-end-wrench": "metric spanner hand wrench",
    "oil-filter-strap-wrench": "fluid oil coolant brake service",
    "oil-filter-chain-wrench": "fluid oil coolant brake service",
    "oil-filter-pliers": "fluid oil coolant brake service",
    "three-jaw-oil-filter-wrench": "fluid oil coolant brake service",
    "spark-plug-socket-5-8-in": "automotive mechanic specialty tool",
    "3-8-in-drive-ratchet": "socket wrench handle",
    "3-8-in-drive-6-in-extension": "socket extension",
    "portable-air-compressor": "shop safety protection equipment",
    "air-blow-gun": "shop safety protection equipment",
}

REFERENCE_ALIASES: dict[str, tuple[str, ...]] = {
    "2-ton-hydraulic-floor-jack": ("Jack + rated jack stands", "jack and rated jack stands"),
    "2-ton-jack-stand-pair": ("Jack + rated jack stands", "jack and rated jack stands"),
    "rubber-wheel-chock-pair": ("Wheel chocks",),
    "metal-wheel-chock-pair": ("Wheel chocks",),
    "1-2-in-drive-19-mm-standard-socket": ("19 mm lug socket", "wheel lug socket"),
    "3-8-in-drive-19-mm-standard-socket": ("19 mm lug socket", "wheel lug socket"),
    "1-2-in-drive-torque-wrench": ("Torque wrench (80 lb-ft capable)", "80 lb-ft torque wrench"),
    "1-4-in-drive-torque-wrench": ("Torque wrench (13 lb-ft capable)", "13 lb-ft torque wrench"),
    "brake-caliper-piston-compressor": ("Brake piston compressor",),
    "coolant-funnel-kit": ("Coolant funnel / spill-free funnel",),
    "spill-free-coolant-funnel": ("Coolant funnel / spill-free funnel",),
    "hose-clamp-pliers": ("Pliers / hose-clamp pliers", "hose-clamp pliers"),
    "safety-glasses-clear": ("Eye protection", "Gloves + eye protection"),
    "mechanic-gloves-nitrile-coated": ("Gloves + eye protection",),
    "3-8-in-drive-14-mm-standard-socket": ("14 mm socket/wrench",),
    "14-mm-open-end-wrench": ("14 mm socket/wrench",),
    "oil-filter-strap-wrench": ("Oil-filter wrench",),
    "oil-filter-chain-wrench": ("Oil-filter wrench",),
    "oil-filter-pliers": ("Oil-filter wrench",),
    "three-jaw-oil-filter-wrench": ("Oil-filter wrench",),
    "spark-plug-socket-5-8-in": ("5/8 in spark-plug socket",),
    "3-8-in-drive-ratchet": ("Ratchet + extensions",),
    "3-8-in-drive-6-in-extension": ("Ratchet + extensions",),
    "portable-air-compressor": ("Compressed-air / debris removal method",),
    "air-blow-gun": ("Compressed-air / debris removal method",),
}

REFERENCE_ADDITIONS: tuple[dict[str, str], ...] = (
    {
        "catalog_key": "metric-socket-and-ratchet-set",
        "category": "wrenches-sockets",
        "name": "Metric socket and ratchet set",
        "keywords": "Socket/ratchet set Basic metric socket set metric socket set ratchet set",
        "visual_key": "socket",
    },
    {
        "catalog_key": "a-c-refrigerant-recovery-recharge-machine",
        "category": "specialty-automotive",
        "name": "A/C refrigerant recovery/recharge machine",
        "keywords": "Certified refrigerant recovery/recharge equipment AC A/C refrigerant recovery recharge service machine",
        "visual_key": "specialty",
    },
    {
        "catalog_key": "service-information-wiring-reference",
        "category": "other",
        "name": "Service information / wiring reference",
        "keywords": "Service information / wiring reference repair manual wiring diagram service data reference",
        "visual_key": "other",
    },
)

MANUAL_REFERENCE_QUERY_TARGETS: dict[str, tuple[str, ...]] = {
    "Jack + rated jack stands": ("2-ton-hydraulic-floor-jack", "2-ton-jack-stand-pair"),
    "Wheel chocks": ("rubber-wheel-chock-pair", "metal-wheel-chock-pair"),
    "19 mm lug socket": ("1-2-in-drive-19-mm-standard-socket", "3-8-in-drive-19-mm-standard-socket"),
    "Torque wrench (80 lb-ft capable)": ("1-2-in-drive-torque-wrench",),
    "Tire pressure gauge": ("tire-pressure-gauge-digital",),
    "Socket/ratchet set": ("metric-socket-and-ratchet-set",),
    "Torque wrench": ("1-2-in-drive-torque-wrench",),
    "Brake piston compressor": ("brake-caliper-piston-compressor",),
    "Drain pan": ("drain-pan-8-qt",),
    "Coolant funnel / spill-free funnel": ("coolant-funnel-kit", "spill-free-coolant-funnel"),
    "Pliers / hose-clamp pliers": ("hose-clamp-pliers",),
    "Gloves + eye protection": ("mechanic-gloves-nitrile-coated", "safety-glasses-clear"),
    "14 mm socket/wrench": ("3-8-in-drive-14-mm-standard-socket", "14-mm-open-end-wrench"),
    "Oil-filter wrench": ("oil-filter-strap-wrench",),
    "Funnel": ("transmission-fluid-funnel",),
    "Certified refrigerant recovery/recharge equipment": ("a-c-refrigerant-recovery-recharge-machine",),
    "Eye protection": ("safety-glasses-clear",),
    "5/8 in spark-plug socket": ("spark-plug-socket-5-8-in",),
    "Ratchet + extensions": ("3-8-in-drive-ratchet", "3-8-in-drive-6-in-extension"),
    "Torque wrench (13 lb-ft capable)": ("1-4-in-drive-torque-wrench",),
    "Compressed-air / debris removal method": ("portable-air-compressor", "air-blow-gun"),
    "OBD-II scan tool": ("obd-ii-scan-tool",),
    "Digital multimeter": ("digital-multimeter",),
    "Basic metric socket set": ("metric-socket-and-ratchet-set",),
    "Service information / wiring reference": ("service-information-wiring-reference",),
}


def reference_keywords(catalog_key: str) -> str:
    base = REFERENCE_BASE_KEYWORDS[catalog_key]
    return " ".join((base, *REFERENCE_ALIASES[catalog_key]))


def augment_equipment_catalog_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    output = [dict(row) for row in rows]
    by_key = {row["catalog_key"]: row for row in output}

    missing_alias_targets = sorted(set(REFERENCE_ALIASES) - set(by_key))
    if missing_alias_targets:
        raise RuntimeError(
            "manual reference aliases point at missing base catalog items: "
            + ", ".join(missing_alias_targets)
        )

    for catalog_key in REFERENCE_ALIASES:
        by_key[catalog_key]["keywords"] = reference_keywords(catalog_key)

    for addition in REFERENCE_ADDITIONS:
        if addition["catalog_key"] in by_key:
            raise RuntimeError(f"manual reference addition already exists: {addition['catalog_key']}")
        row = dict(addition)
        output.append(row)
        by_key[row["catalog_key"]] = row

    return output
