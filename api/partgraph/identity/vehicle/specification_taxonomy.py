from __future__ import annotations

import json
import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from .taxonomy import (
    canonical_body_style,
    canonical_drivetrain,
    canonical_engine,
    canonical_make,
    canonical_model,
    canonical_transmission,
    canonical_trim,
    clean_display,
    compact_key,
)

TECHNICAL_PROFILE_VERSION = 1

_ENGINE_DISPLACEMENT = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:l|liter|liters|litre|litres)\b",
    re.I,
)
_ENGINE_CYLINDERS = re.compile(
    r"\b([2-9]|1[0-2])\s*[\s-]*(?:cyl(?:inder)?s?|cylinders?)\b",
    re.I,
)
_ENGINE_ARCHITECTURE = (
    (re.compile(r"\b(?:inline[\s-]*3|i3|l3)\b", re.I), "I3"),
    (re.compile(r"\b(?:inline[\s-]*4|i4|l4)\b", re.I), "I4"),
    (re.compile(r"\b(?:inline[\s-]*5|i5|l5)\b", re.I), "I5"),
    (re.compile(r"\b(?:inline[\s-]*6|i6|l6)\b", re.I), "I6"),
    (re.compile(r"\bflat[\s-]*4\b|\bh4\b", re.I), "H4"),
    (re.compile(r"\bflat[\s-]*6\b|\bh6\b", re.I), "H6"),
    (re.compile(r"\bv[\s-]*6\b", re.I), "V6"),
    (re.compile(r"\bv[\s-]*8\b", re.I), "V8"),
    (re.compile(r"\bv[\s-]*10\b", re.I), "V10"),
    (re.compile(r"\bv[\s-]*12\b", re.I), "V12"),
)
_HORSEPOWER = re.compile(r"\b(\d{2,4}(?:\.\d+)?)\s*(?:hp|horsepower|bhp)\b", re.I)
_TORQUE_LB_FT = re.compile(
    r"\b(\d{2,4}(?:\.\d+)?)\s*(?:lb[\s.-]*(?:ft|feet)|ft[\s.-]*lb|pound[\s-]*feet)\b",
    re.I,
)
_VALVE_COUNT = re.compile(r"\b(\d{1,2})\s*[\s-]*(?:valve|valves|v)\b", re.I)
_TRANSMISSION_SPEED = re.compile(r"\b(\d{1,2})\s*[\s-]*(?:speed|spd)\b", re.I)
_TRANSMISSION_COMPACT = re.compile(r"\b(\d{1,2})(?:at|mt|dct)\b", re.I)

_TECHNOLOGY_PATTERNS = (
    (re.compile(r"\bi[\s-]*vtec\b", re.I), "i-VTEC"),
    (re.compile(r"\bvtec[\s-]*e\b", re.I), "VTEC-E"),
    (re.compile(r"\bvtec\b", re.I), "VTEC"),
    (re.compile(r"\bvvt[\s-]*i\b", re.I), "VVT-i"),
    (re.compile(r"\bvvti\b", re.I), "VVT-i"),
    (re.compile(r"\bavcs\b", re.I), "AVCS"),
)


def _number(value: float) -> int | float:
    rounded = round(float(value), 4)
    return int(rounded) if rounded.is_integer() else rounded


def split_engine_descriptor(value: str | None) -> dict[str, object]:
    """Split a human engine description into independent mechanical facts.

    This intentionally does not infer an inline architecture from a generic
    "4-cylinder" label; a boxer/flat engine is also four-cylinder. Only facts
    explicit in the descriptor are returned.
    """
    if not value:
        return {}
    text = clean_display(value)
    fields: dict[str, object] = {}

    displacement = _ENGINE_DISPLACEMENT.search(text)
    if displacement:
        fields["powertrain.engine.displacement_l"] = _number(float(displacement.group(1)))

    cylinders = _ENGINE_CYLINDERS.search(text)
    if cylinders:
        fields["powertrain.engine.cylinders"] = int(cylinders.group(1))

    for pattern, label in _ENGINE_ARCHITECTURE:
        if pattern.search(text):
            fields["powertrain.engine.architecture"] = label
            break

    horsepower = _HORSEPOWER.search(text)
    if horsepower:
        fields["performance.horsepower_hp"] = _number(float(horsepower.group(1)))

    torque = _TORQUE_LB_FT.search(text)
    if torque:
        fields["performance.torque_lb_ft"] = _number(float(torque.group(1)))

    technologies: list[str] = []
    if re.search(r"\bi[\s-]*vtec\b", text, re.I):
        technologies.append("i-VTEC")
    elif re.search(r"\bvtec[\s-]*e\b", text, re.I):
        technologies.append("VTEC-E")
    elif re.search(r"\bvtec\b", text, re.I):
        technologies.append("VTEC")
    for pattern, label in _TECHNOLOGY_PATTERNS[3:]:
        if pattern.search(text) and label not in technologies:
            technologies.append(label)
    if technologies:
        fields["powertrain.engine.technology"] = technologies

    lowered = text.casefold()
    if "turbo" in lowered:
        fields["powertrain.engine.aspiration"] = "Turbocharged"
    elif "supercharged" in lowered:
        fields["powertrain.engine.aspiration"] = "Supercharged"

    if "plug-in hybrid" in lowered or "plug in hybrid" in lowered or "phev" in lowered:
        fields["powertrain.electrification"] = "PHEV"
    elif "hybrid" in lowered:
        fields["powertrain.electrification"] = "Hybrid"
    elif "electric" in lowered and "engine" not in lowered:
        fields["powertrain.electrification"] = "EV"

    if "diesel" in lowered:
        fields["powertrain.fuel_type"] = "Diesel"

    if re.search(r"\bdohc\b", text, re.I):
        fields["powertrain.engine.valvetrain"] = "DOHC"
    elif re.search(r"\bsohc\b", text, re.I):
        fields["powertrain.engine.valvetrain"] = "SOHC"

    valves = _VALVE_COUNT.search(text)
    if valves:
        fields["powertrain.engine.valves"] = int(valves.group(1))

    return fields


def split_transmission_descriptor(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    text = clean_display(value)
    lowered = compact_key(text)
    fields: dict[str, object] = {}

    if "ecvt" in lowered or "electroniccvt" in lowered:
        family = "eCVT"
    elif (
        "cvt" in lowered
        or "continuouslyvariable" in lowered
        or "variablegearratios" in lowered
    ):
        family = "CVT"
    elif "dct" in lowered or "dualclutch" in lowered:
        family = "DCT"
    elif "manual" in lowered or lowered.endswith("mt"):
        family = "Manual"
    elif "automatic" in lowered or "auto" in lowered or lowered.endswith("at"):
        family = "Automatic"
    else:
        canonical = canonical_transmission(text)
        family = canonical if canonical in {"CVT", "eCVT", "DCT", "Manual", "Automatic"} else None

    if family:
        fields["transmission.family"] = family

    speed = _TRANSMISSION_SPEED.search(text) or _TRANSMISSION_COMPACT.search(lowered)
    if speed:
        fields["transmission.speeds"] = int(speed.group(1))

    return fields


def seed_profile_fields(configuration: Any) -> dict[str, object]:
    """Convert one seed VehicleConfiguration into independent expected facts."""
    fields: dict[str, object] = {
        "identity.year": int(configuration.year),
        "identity.make": canonical_make(str(configuration.make)),
        "identity.model": canonical_model(str(configuration.model)),
    }
    trim = canonical_trim(getattr(configuration, "trim", None))
    if trim:
        fields["identity.trim"] = trim
    body_style = canonical_body_style(getattr(configuration, "body_style", None))
    if body_style:
        fields["identity.body_style"] = body_style
    drivetrain = canonical_drivetrain(getattr(configuration, "drivetrain", None))
    if drivetrain:
        fields["identity.drivetrain"] = drivetrain
    fields.update(split_engine_descriptor(getattr(configuration, "engine", None)))
    fields.update(split_transmission_descriptor(getattr(configuration, "transmission", None)))
    return fields


def core_configuration_fields(configuration: Any) -> dict[str, object]:
    """Facts the seed row itself asserts and therefore must corroborate.

    The original engine/transmission strings are not atomic identity fields.
    They are split first, but every mechanical fact asserted by the seed row
    must still be corroborated before that candidate row is called verified.
    """
    return seed_profile_fields(configuration)


def normalize_observation_value(field: str, value: object) -> object:
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _number(float(value))
    if isinstance(value, list):
        normalized = [normalize_observation_value(field, item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))
    if not isinstance(value, str):
        return value

    cleaned = clean_display(value)
    if field == "identity.make":
        return canonical_make(cleaned)
    if field == "identity.model":
        return canonical_model(cleaned)
    if field == "identity.trim":
        return canonical_trim(cleaned)
    if field == "identity.body_style":
        return canonical_body_style(cleaned)
    if field == "identity.drivetrain":
        return canonical_drivetrain(cleaned)
    if field in {"identity.transmission", "transmission.family"}:
        return canonical_transmission(cleaned)
    if field == "powertrain.engine.description":
        return canonical_engine(cleaned)
    if field == "powertrain.engine.architecture":
        return cleaned.upper().replace("INLINE-", "I").replace("INLINE ", "I")
    if field == "powertrain.fuel_type":
        key = compact_key(cleaned)
        if "diesel" in key:
            return "Diesel"
        if "electricity" in key or key in {"electric", "electricity"}:
            return "Electricity"
        if "e85" in key or "flexfuel" in key:
            return "E85/Flex Fuel"
        if "gasoline" in key or "petrol" in key or "unleaded" in key or key == "gas":
            return "Gasoline"
        return cleaned
    if field in {"powertrain.engine.technology", "safety.systems"}:
        return cleaned
    return cleaned


def observation_comparison_key(field: str, value: object) -> str:
    normalized = normalize_observation_value(field, value)
    if normalized is None:
        return "null"
    if isinstance(normalized, str):
        if field in {
            "identity.make",
            "identity.model",
            "identity.trim",
            "identity.body_style",
            "identity.drivetrain",
            "transmission.family",
            "powertrain.engine.architecture",
            "powertrain.engine.aspiration",
            "powertrain.electrification",
            "powertrain.fuel_type",
            "powertrain.engine.valvetrain",
            "powertrain.engine.technology",
        }:
            return compact_key(normalized)
        return " ".join(normalized.casefold().split())
    if isinstance(normalized, list):
        parts = sorted(observation_comparison_key(field, item) for item in normalized)
        return json.dumps(parts, separators=(",", ":"))
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def technical_section(field: str) -> str:
    if field.startswith("identity.") or field.startswith("classification."):
        return "identity"
    if field.startswith("powertrain.") or field.startswith("transmission."):
        return "powertrain"
    if field.startswith("performance."):
        return "performance"
    if field.startswith("efficiency.") or field.startswith("emissions."):
        return "efficiency_emissions"
    if field.startswith("dimensions_weight."):
        return "dimensions_weight"
    if field.startswith("capacity."):
        return "capacities"
    if (
        field.startswith("chassis.")
        or field.startswith("steering.")
        or field.startswith("suspension.")
    ):
        return "chassis"
    if field.startswith("brakes."):
        return "brakes"
    if field.startswith("wheels_tires."):
        return "wheels_tires"
    if field.startswith("service.") or field.startswith("fluids."):
        return "service_fluids"
    if field.startswith("electrical.") or field.startswith("charging."):
        return "electrical_charging"
    if field.startswith("safety."):
        return "safety"
    return "other_technical"


def section_summary(field_results: list[Mapping[str, object]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for result in field_results:
        field = result.get("field")
        status = result.get("status")
        if not isinstance(field, str) or not isinstance(status, str):
            continue
        section = technical_section(field)
        counts = summary.setdefault(
            section,
            {"verified": 0, "manufacturer_reported": 0, "candidate": 0, "conflict": 0},
        )
        if status in counts:
            counts[status] += 1
    return summary


def core_verification_decision(
    configuration: Any,
    field_results: list[Mapping[str, object]],
) -> dict[str, object]:
    expected = core_configuration_fields(configuration)
    by_field = {
        result.get("field"): result
        for result in field_results
        if isinstance(result.get("field"), str)
    }
    checks: list[dict[str, object]] = []
    has_conflict = False
    all_verified = bool(expected)
    match_counts: list[int] = []

    for field, expected_value in expected.items():
        result = by_field.get(field)
        status = result.get("status") if isinstance(result, Mapping) else None
        selected = result.get("selected_value") if isinstance(result, Mapping) else None
        selected_matches = (
            status == "verified"
            and observation_comparison_key(field, selected)
            == observation_comparison_key(field, expected_value)
        )
        if status == "conflict":
            has_conflict = True
        if not selected_matches:
            all_verified = False
        match_count = int(result.get("match_count", 0)) if isinstance(result, Mapping) else 0
        if selected_matches:
            match_counts.append(match_count)
        checks.append(
            {
                "field": field,
                "expected_value": expected_value,
                "status": status or "missing",
                "selected_value": selected,
                "match_count": match_count,
                "verified": selected_matches,
            }
        )

    return {
        "verified": all_verified and not has_conflict,
        "conflict": has_conflict,
        "source_match_floor": min(match_counts) if all_verified and match_counts else 0,
        "required_fields": checks,
    }
