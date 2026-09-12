from __future__ import annotations

from collections.abc import Iterable

ENGINE_OIL_GRADES: dict[str, tuple[str, tuple[str, ...]]] = {
    "full-synthetic": (
        "Full synthetic",
        (
            "0W-8", "0W-12", "0W-16", "0W-20", "0W-30", "0W-40",
            "5W-20", "5W-30", "5W-40", "5W-50",
            "10W-30", "10W-40", "10W-50", "10W-60",
            "15W-50", "20W-50",
        ),
    ),
    "synthetic-blend": (
        "Synthetic blend",
        ("0W-20", "5W-20", "5W-30", "10W-30", "10W-40", "15W-40", "20W-50"),
    ),
    "conventional": (
        "Conventional",
        ("5W-20", "5W-30", "10W-30", "10W-40", "15W-40", "20W-50"),
    ),
    "high-mileage-full-synthetic": (
        "High-mileage full synthetic",
        ("0W-20", "5W-20", "5W-30", "10W-30", "10W-40"),
    ),
    "high-mileage-synthetic-blend": (
        "High-mileage synthetic blend",
        ("0W-20", "5W-20", "5W-30", "10W-30", "10W-40", "20W-50"),
    ),
    "high-mileage-conventional": (
        "High-mileage conventional",
        ("10W-30", "10W-40"),
    ),
}

COOLANT_CHEMISTRIES: tuple[tuple[str, str], ...] = (
    ("IAT", "inorganic additive technology"),
    ("OAT", "organic acid technology"),
    ("HOAT", "hybrid organic acid technology"),
    ("P-HOAT", "phosphated hybrid organic acid technology"),
    ("Si-OAT", "silicated organic acid technology"),
)

WASHER_FLUID_ITEMS: tuple[tuple[str, str], ...] = (
    ("All-season windshield washer fluid", "all season washer fluid windshield cleaning"),
    ("Summer bug-remover windshield washer fluid", "summer bug wash washer fluid windshield cleaning"),
    ("Winter de-icer windshield washer fluid", "winter deicer de-icer washer fluid windshield cleaning freezing"),
    ("Extreme-cold windshield washer fluid", "extreme cold low temperature winter washer fluid windshield cleaning"),
)

LUG_NUT_THREAD_SIZES: tuple[str, ...] = (
    "7/16-20",
    "1/2-20",
    "9/16-18",
    "M12 x 1.25",
    "M12 x 1.5",
    "M12 x 1.75",
    "M14 x 1.5",
    "M14 x 2.0",
)

RETIRED_CATALOG_KEYS = {
    "a-c-refrigerant-recovery-recharge-machine",
    "service-information-wiring-reference",
}

KEYWORD_UPDATES: dict[str, str] = {
    "coolant-funnel-kit": (
        "fluid oil coolant brake service coolant filling funnel radiator fill funnel "
        "coolant air bleed funnel coolant burping funnel no-spill funnel"
    ),
    "spill-free-coolant-funnel": (
        "fluid oil coolant brake service spill-free funnel no-spill coolant filling funnel "
        "coolant air bleed funnel coolant burping funnel radiator fill bleed funnel"
    ),
}


def _slug(value: str) -> str:
    output: list[str] = []
    dash = False
    for character in value.lower():
        if character.isalnum():
            output.append(character)
            dash = False
        elif not dash:
            output.append("-")
            dash = True
    return "".join(output).strip("-")


def _row(category: str, name: str, keywords: str, visual_key: str) -> dict[str, str]:
    return {
        "catalog_key": _slug(name),
        "category": category,
        "name": name,
        "keywords": keywords,
        "visual_key": visual_key,
    }


def _engine_oil_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, (formulation, grades) in ENGINE_OIL_GRADES.items():
        for grade in grades:
            compact_grade = grade.replace("-", "").lower()
            rows.append(
                _row(
                    "engine-oil",
                    f"{formulation} engine oil SAE {grade}",
                    f"motor oil engine lubricant SAE {grade} {compact_grade} {formulation.lower()}",
                    "oil",
                )
            )
    return rows


def _coolant_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for abbreviation, expansion in COOLANT_CHEMISTRIES:
        rows.append(
            _row(
                "coolant-antifreeze",
                f"{abbreviation} coolant/antifreeze concentrate",
                f"engine coolant antifreeze concentrate {abbreviation} {expansion}",
                "coolant",
            )
        )
        rows.append(
            _row(
                "coolant-antifreeze",
                f"{abbreviation} coolant/antifreeze 50/50 prediluted",
                f"engine coolant antifreeze premix premixed prediluted 50/50 {abbreviation} {expansion}",
                "coolant",
            )
        )
    return rows


def _washer_rows() -> list[dict[str, str]]:
    return [_row("washer-fluid", name, keywords, "washer-fluid") for name, keywords in WASHER_FLUID_ITEMS]


def _lug_nut_rows() -> list[dict[str, str]]:
    return [
        _row(
            "wheel-hardware",
            f"Wheel lug nut {thread_size}",
            f"wheel lug nut wheel nut stud nut thread {thread_size.replace(' ', '')}",
            "lug",
        )
        for thread_size in LUG_NUT_THREAD_SIZES
    ]


def _ac_service_rows() -> list[dict[str, str]]:
    return [
        _row(
            "specialty-automotive",
            "R-134a A/C refrigerant recover recycle recharge machine",
            "R134a R-134a air conditioning AC A/C refrigerant recovery recycling evacuation recharge service machine",
            "specialty",
        ),
        _row(
            "specialty-automotive",
            "R-1234yf A/C refrigerant recover recycle recharge machine",
            "R1234yf R-1234yf air conditioning AC A/C refrigerant recovery recycling evacuation recharge service machine",
            "specialty",
        ),
    ]


def catalog_additions() -> list[dict[str, str]]:
    return [
        *_engine_oil_rows(),
        *_coolant_rows(),
        *_washer_rows(),
        *_lug_nut_rows(),
        *_ac_service_rows(),
    ]


def current_inventory_catalog(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    output = [dict(row) for row in rows if row["catalog_key"] not in RETIRED_CATALOG_KEYS]
    by_key = {row["catalog_key"]: row for row in output}

    for catalog_key, keywords in KEYWORD_UPDATES.items():
        if catalog_key not in by_key:
            raise RuntimeError(f"inventory keyword target is missing: {catalog_key}")
        by_key[catalog_key]["keywords"] = keywords

    for addition in catalog_additions():
        key = addition["catalog_key"]
        if key in by_key:
            raise RuntimeError(f"inventory catalog addition already exists: {key}")
        row = dict(addition)
        output.append(row)
        by_key[key] = row

    return output
